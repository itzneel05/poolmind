"""
poolmind CLI - main entry point.
Command pattern: pool <verb> <args>
"""

import json
import logging
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app import db
from app.add_resource import add_from_url, add_manual
from app.obsidian_writer import (
    move_note_to_trash,
    restore_note_from_trash,
    delete_note_by_id,
)
from app.notion_sync import archive_resource, unarchive_resource
from app.audit import (
    dead_check,
    full_audit,
    get_low_confidence_resources,
    run_gap_report,
)
from app.dedupe import find_all_duplicates
from app.feedback_tracker import (
    get_all_task_stats,
    get_evolution_history,
    log_user_correction,
    REQUIRED_FIELDS as FEEDBACK_TASKS,
)
from app.prompt_evolution import (
    evolve_prompt,
    evolve_all,
    list_backups,
    restore_prompt,
)
from app.search import get_random, get_recent, get_untouched, list_by_filter, search
from models.resource import Resource

app = typer.Typer(
    name="pool",
    help="poolmind - Cybersecurity Resource Pool",
    add_completion=False,
)
import io

console = Console(
    file=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
)
logger = logging.getLogger(__name__)


@app.command("init")
def cmd_init():
    """Initialize the poolmind database."""
    from scripts.init_db import init_db

    init_db()
    console.print(
        Panel(
            "[green]poolmind initialized.[/green]\n\n"
            "Next: [bold]pool add <url>[/bold] to add your first resource.",
            title="poolmind",
        )
    )


@app.command("add")
def cmd_add(
    url: str = typer.Argument(...),
    notes: str = typer.Option("", "--notes", "-n", help="Personal notes"),
    no_ai: bool = typer.Option(False, "--no-ai", help="Disable AI enrichment"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip duplicate check"),
    no_notion: bool = typer.Option(False, "--no-notion", help="Skip Notion sync"),
    no_obsidian: bool = typer.Option(
        False, "--no-obsidian", help="Skip Obsidian write"
    ),
):
    """Add a resource by URL."""
    with console.status(f"[bold green]Processing {url}...[/bold green]"):
        resource = add_from_url(
            url=url,
            notes=notes,
            ai_disabled=no_ai,
            skip_notion=no_notion,
            skip_obsidian=no_obsidian,
            force=force,
        )
    if resource:
        _print_resource_card(resource, action="Added")
    else:
        console.print("[red]Failed to add resource.[/red]")
        raise typer.Exit(1)


@app.command("add-manual")
def cmd_add_manual(
    title: str = typer.Option(..., "--title", "-t", help="Resource title"),
    url: str = typer.Option("local", "--url", "-u", help="URL (or local)"),
    type_: str = typer.Option("note", "--type", help="Resource type"),
    domain: str = typer.Option("general", "--domain", "-d", help="Domain"),
    notes: str = typer.Option("", "--notes", "-n", help="Notes"),
):
    """Add a resource manually (no URL extraction)."""
    resource = add_manual(
        {
            "title": title,
            "url": url,
            "type": type_,
            "domain": domain,
            "notes": notes,
        }
    )
    if resource:
        _print_resource_card(resource, action="Added (manual)")
    else:
        console.print("[red]Failed to add resource.[/red]")
        raise typer.Exit(1)


@app.command("bulk")
def cmd_bulk(
    file: Optional[str] = typer.Option(
        None, "--file", "-f", help="File with one URL per line"
    ),
    no_ai: bool = typer.Option(False, "--no-ai", help="Disable AI enrichment"),
):
    """Bulk add resources from a file or stdin (one URL per line)."""
    if file:
        with open(file) as f:
            urls = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    else:
        console.print(
            "[yellow]Paste URLs (one per line). Press Ctrl+D when done:[/yellow]"
        )
        urls = []
        try:
            for line in sys.stdin:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
        except EOFError:
            pass
    if not urls:
        console.print("[yellow]No URLs provided.[/yellow]")
        return
    console.print(f"[bold]Processing {len(urls)} URLs...[/bold]")
    success = 0
    failed = 0
    for url in urls:
        with console.status(f"Processing {url[:60]}..."):
            resource = add_from_url(url=url, ai_disabled=no_ai)
        if resource:
            console.print(f"[green]{resource.title[:60]}[/green]")
            success += 1
        else:
            console.print(f"[red]Failed: {url[:60]}[/red]")
            failed += 1
    console.print(f"\n[bold]Done: {success} added, {failed} failed[/bold]")


@app.command("ingest")
def cmd_ingest(
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Input file path"),
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Inline text input"),
    no_ai: bool = typer.Option(False, "--no-ai", help="Disable AI enrichment"),
    no_notion: bool = typer.Option(False, "--no-notion", help="Skip Notion sync"),
    no_obsidian: bool = typer.Option(
        False, "--no-obsidian", help="Skip Obsidian write"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse only, do not ingest"),
    show_parsed: bool = typer.Option(
        False, "--show-parsed", help="Show parsed entries before ingesting"
    ),
):
    """
    Smart bulk ingest from file or text.

    Handles URLs, title-URL pairs, markdown links, Notion pages, title-only entries.

    Examples:
        pool ingest --file resources.txt
        pool ingest --text "Title - https://example.com"
        pool ingest --dry-run --show-parsed --file resources.txt
    """
    from app.bulk_parser import (
        parse_bulk_input,
        parse_bulk_file,
        summarize_parse_results,
    )
    from app.ingest_router import ingest_entries, build_ingestion_report

    if file:
        console.print(f"[dim]Reading: {file}[/dim]")
        entries = parse_bulk_file(file)
    elif text:
        entries = parse_bulk_input(text)
    else:
        console.print(
            "[yellow]Paste your resources below. Press Ctrl+Z then Enter when done:[/yellow]"
        )
        lines = []
        try:
            for line in sys.stdin:
                lines.append(line)
        except EOFError:
            pass
        entries = parse_bulk_input("\n".join(lines))

    if not entries:
        console.print("[yellow]No entries parsed from input.[/yellow]")
        return

    summary = summarize_parse_results(entries)
    console.print(f"\n[bold]Parsed {summary['total']} entries:[/bold]")
    for type_name, count in summary["by_type"].items():
        console.print(f"  {type_name}: {count}")
    if summary["title_only"] > 0:
        console.print(
            f"  [yellow]! {summary['title_only']} entries have no URL (will be stored as local)[/yellow]"
        )
    if summary["low_confidence"] > 0:
        console.print(
            f"  [dim]! {summary['low_confidence']} entries parsed with low confidence[/dim]"
        )

    if show_parsed:
        console.print("\n[bold]Parsed entries:[/bold]")
        for i, e in enumerate(entries, 1):
            url_str = e.url[:60] if e.url else "[dim]no url[/dim]"
            title_str = e.title[:40] if e.title else "[dim]no title[/dim]"
            console.print(
                f"  {i:3}. [{e.entry_type}] {title_str} | {url_str} "
                f"[dim](conf: {e.confidence:.2f})[/dim]"
            )

    if dry_run:
        console.print("\n[yellow]DRY RUN - nothing ingested.[/yellow]")
        return

    if summary["total"] > 20:
        confirmed = typer.confirm(f"Ingest all {summary['total']} entries?")
        if not confirmed:
            console.print("[yellow]Aborted.[/yellow]")
            return

    console.print(f"\n[bold]Ingesting {summary['total']} entries...[/bold]\n")
    results = []

    def on_progress(current, total, result):
        entry = result.entry
        title = (entry.title or entry.url or "?")[:50]
        action_color = {
            "added": "green",
            "duplicate": "yellow",
            "failed": "red",
            "needs_review": "cyan",
            "skipped": "dim",
        }.get(result.action, "white")
        console.print(
            f"  [{current:3}/{total}] "
            f"[{action_color}]{result.action:12}[/{action_color}] "
            f"{title}" + (f" [dim]({result.error})[/dim]" if result.error else "")
        )
        results.append(result)

    ingest_entries(
        entries=entries,
        ai_disabled=no_ai,
        skip_notion_sync=no_notion,
        skip_obsidian=no_obsidian,
        dry_run=False,
        on_progress=on_progress,
    )

    report = build_ingestion_report(results)

    console.print(
        Panel(
            f"[green][+] Added:[/green]        {report['added']}\n"
            f"[yellow][=] Duplicates:[/yellow]   {report['duplicates']}\n"
            f"[cyan][?] Needs review:[/cyan]  {report['needs_review']}\n"
            f"[red][-] Failed:[/red]         {report['failed']}\n"
            f"[dim][ ] Skipped:[/dim]        {report['skipped']}\n"
            f"[dim][~] Avg time:[/dim]       {report['avg_time_ms']}ms/entry",
            title="[bold]Ingestion Complete[/bold]",
            border_style="green" if report["failed"] == 0 else "yellow",
        )
    )

    if report["failed_entries"]:
        console.print("\n[bold red]Failed entries:[/bold red]")
        for f in report["failed_entries"]:
            console.print(f"  Line {f['line']}: {f['raw']} -> {f['error']}")

    if report["needs_review_entries"]:
        console.print("\n[bold cyan]Needs manual review (no URL):[/bold cyan]")
        for r in report["needs_review_entries"]:
            console.print(f"  [{r['id']}] {r['title']}")
        console.print("[dim]Use: pool edit <id> to add URL and metadata[/dim]")


@app.command("search")
def cmd_search(
    query: str = typer.Argument(""),
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Domain filter"),
    type_: Optional[str] = typer.Option(None, "--type", "-t", help="Type filter"),
    skill: Optional[str] = typer.Option(
        None, "--skill", "-s", help="Skill level filter"
    ),
    format_: Optional[str] = typer.Option(None, "--format", help="Format filter"),
    cost: Optional[str] = typer.Option(None, "--cost", help="Cost filter"),
    min_quality: Optional[int] = typer.Option(
        None, "--min-quality", "-q", help="Minimum quality score"
    ),
    limit: int = typer.Option(10, "--limit", "-l", help="Result limit"),
    nl: bool = typer.Option(False, "--nl", help="Natural language query parsing"),
):
    """Search the resource pool."""
    with console.status("[bold green]Searching...[/bold green]"):
        results = search(
            query=query,
            domain=domain,
            type_=type_,
            skill_level=skill,
            format_=format_,
            cost=cost,
            min_quality=min_quality,
            limit=limit,
            natural_language=nl,
        )
    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return
    console.print(f"\n[bold]Found {len(results)} result(s)[/bold]\n")
    for i, r in enumerate(results, 1):
        _print_search_card(i, r)


@app.command("find")
def cmd_find(
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Domain filter"),
    type_: Optional[str] = typer.Option(None, "--type", "-t", help="Type filter"),
    skill: Optional[str] = typer.Option(
        None, "--skill", "-s", help="Skill level filter"
    ),
    state: Optional[str] = typer.Option(
        None, "--state", help="Consumption state filter"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="Result limit"),
):
    """Filter resources without text search."""
    results = list_by_filter(
        domain=domain,
        type_=type_,
        skill_level=skill,
        consumption_state=state,
        limit=limit,
    )
    _print_results_table(results)


@app.command("get")
def cmd_get(
    resource_id: str = typer.Argument(...),
):
    """Get a resource by ID."""
    resource = db.get_resource(resource_id)
    if resource:
        _print_resource_full(resource)
    else:
        console.print(f"[red]Resource not found: {resource_id}[/red]")
        raise typer.Exit(1)


@app.command("recent")
def cmd_recent(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of resources"),
):
    """Show recently added resources."""
    results = get_recent(limit=limit)
    _print_results_table(results)


@app.command("random")
def cmd_random():
    """Surface a random forgotten gem."""
    results = get_random(1)
    if results:
        console.print("\n[bold]Random resource from your pool:[/bold]\n")
        _print_resource_full(results[0])
    else:
        console.print("[yellow]Pool is empty.[/yellow]")


@app.command("untouched")
def cmd_untouched(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of resources"),
):
    """Show resources never used (still in saved state)."""
    results = get_untouched(limit=limit)
    console.print(f"\n[bold]{len(results)} untouched resources:[/bold]\n")
    _print_results_table(results)


@app.command("rate")
def cmd_rate(
    resource_id: str = typer.Argument(...),
    score: int = typer.Argument(...),
):
    """Set personal rating for a resource."""
    if not 1 <= score <= 10:
        console.print("[red]Score must be 1-10[/red]")
        raise typer.Exit(1)
    success = db.update_resource(resource_id, {"personal_rating": score})
    if success:
        console.print(f"[green]Rated {resource_id}: {score}/10[/green]")
    else:
        console.print(f"[red]Resource not found: {resource_id}[/red]")


@app.command("note")
def cmd_note(
    resource_id: str = typer.Argument(...),
    text: str = typer.Argument(...),
):
    """Add or update notes for a resource."""
    resource = db.get_resource(resource_id)
    if not resource:
        console.print(f"[red]Not found: {resource_id}[/red]")
        raise typer.Exit(1)
    existing = resource.notes or ""
    new_note = f"{existing}\n{text}".strip() if existing else text
    db.update_resource(resource_id, {"notes": new_note})
    console.print(f"[green]Note updated for {resource_id}[/green]")


@app.command("state")
def cmd_state(
    resource_id: str = typer.Argument(...),
    state: str = typer.Argument(...),
):
    """Update consumption state for a resource."""
    valid = {"saved", "skimmed", "studied", "mastered", "applied"}
    if state not in valid:
        console.print(f"[red]Invalid state. Must be one of: {', '.join(valid)}[/red]")
        raise typer.Exit(1)
    db.update_resource(resource_id, {"consumption_state": state})
    db.increment_used(resource_id)
    console.print(f"[green]{resource_id} -> {state}[/green]")


@app.command("tag")
def cmd_tag(
    resource_id: str = typer.Argument(...),
    tags: str = typer.Argument(...),
):
    """Add tags to a resource."""
    resource = db.get_resource(resource_id)
    if not resource:
        console.print(f"[red]Not found: {resource_id}[/red]")
        raise typer.Exit(1)
    new_tags = [t.strip() for t in tags.split(",") if t.strip()]
    combined = list(set(resource.tags + new_tags))[:15]
    db.update_resource(resource_id, {"tags": combined})
    console.print(f"[green]Tags updated: {', '.join(combined)}[/green]")


@app.command("archive")
def cmd_archive(
    resource_id: str = typer.Argument(...),
    hard: bool = typer.Option(False, "--hard", help="Hard delete (irreversible)"),
):
    """Archive (soft-delete via consumption_state) or hard-delete a resource."""
    if hard:
        confirm = typer.confirm(f"Permanently delete {resource_id}?")
        if not confirm:
            return
    success = db.delete_resource(resource_id, hard=hard)
    if success:
        action = "deleted" if hard else "archived"
        console.print(f"[green]Resource {action}: {resource_id}[/green]")
    else:
        console.print(f"[red]Not found: {resource_id}[/red]")


@app.command("trash")
def cmd_trash(
    resource_id: str = typer.Argument(..., help="Resource ID to trash"),
    reason: str = typer.Option(None, "--reason", "-r", help="Reason for trashing"),
    no_obsidian: bool = typer.Option(False, "--no-obsidian", help="Skip Obsidian sync"),
    no_notion: bool = typer.Option(False, "--no-notion", help="Skip Notion sync"),
):
    """Soft-delete a resource (moves to trash)."""
    result = db.trash_resources([resource_id], reason=reason)
    if result["trashed"] > 0:
        console.print(f"[green]Trashed: {resource_id}[/green]")
        if not no_obsidian:
            move_note_to_trash(resource_id)
        if not no_notion:
            res = db.get_resource(resource_id, include_trashed=True)
            if res and res.notion_page_id:
                archive_resource(res.notion_page_id)
    else:
        console.print(f"[red]Not found: {resource_id}[/red]")
        raise typer.Exit(1)


@app.command("restore")
def cmd_restore(
    resource_id: str = typer.Argument(..., help="Resource ID to restore"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip conflict check"),
    no_obsidian: bool = typer.Option(False, "--no-obsidian", help="Skip Obsidian sync"),
    no_notion: bool = typer.Option(False, "--no-notion", help="Skip Notion sync"),
):
    """Restore a trashed resource back to the active pool."""
    if not force:
        conflicts = db.check_restore_conflicts([resource_id])
        if conflicts:
            console.print("[yellow]URL conflict detected:[/yellow]")
            for c in conflicts:
                console.print(f"  URL: {c['url']}")
                console.print(f"  Existing: [{c['existing_id']}] {c['existing_title']}")
                console.print(f"  Trashed: [{c['trashed_id']}] (being restored)")
            confirmed = typer.confirm("Restore anyway?")
            if not confirmed:
                console.print("[yellow]Restore cancelled.[/yellow]")
                return
    result = db.restore_resources([resource_id])
    if result["restored"] > 0:
        console.print(f"[green]Restored: {resource_id}[/green]")
        if not no_obsidian:
            restore_note_from_trash(resource_id)
        if not no_notion:
            res = db.get_resource(resource_id)
            if res and res.notion_page_id:
                unarchive_resource(res.notion_page_id)
    else:
        console.print(f"[red]Not found or not trashed: {resource_id}[/red]")
        raise typer.Exit(1)


@app.command("purge")
def cmd_purge(
    resource_id: str = typer.Argument(..., help="Resource ID to permanently delete"),
    no_obsidian: bool = typer.Option(
        False, "--no-obsidian", help="Skip Obsidian clean"
    ),
):
    """Permanently delete a trashed resource."""
    confirm = typer.confirm(f"Permanently purge {resource_id}? This cannot be undone.")
    if not confirm:
        return
    result = db.purge_resources([resource_id])
    if result["purged"] > 0:
        console.print(f"[green]Purged: {resource_id}[/green]")
        if not no_obsidian:
            delete_note_by_id(resource_id)
    else:
        console.print(f"[red]Not found or not trashed: {resource_id}[/red]")
        raise typer.Exit(1)


@app.command("trashed")
def cmd_trashed(
    search: str = typer.Option(None, "--search", "-s", help="Search term"),
    domain: str = typer.Option(None, "--domain", "-d", help="Domain filter"),
    limit: int = typer.Option(20, "--limit", "-l", help="Result limit"),
):
    """List trashed resources."""
    results = db.get_trashed_resources(
        search_q=search,
        domain=domain,
        limit=limit,
    )
    if not results:
        console.print("[yellow]Trash is empty.[/yellow]")
        return
    stats = db.get_trash_stats()
    console.print(f"\n[bold]Trash ({stats['total']} items)[/bold]\n")
    table = Table(show_header=True, header_style="bold red")
    table.add_column("ID", width=10)
    table.add_column("Title", width=40)
    table.add_column("Domain", width=12)
    table.add_column("Deleted", width=20)
    table.add_column("Reason", width=20)
    for r in results:
        table.add_row(
            r["id"] if isinstance(r, dict) else r.id,
            (r["title"] if isinstance(r, dict) else r.title)[:39],
            r["domain"] if isinstance(r, dict) else r.domain,
            (r["deleted_at"] or "")[:16]
            if isinstance(r, dict)
            else (r.deleted_at or "")[:16],
            (r.get("deleted_reason") or "")[:19]
            if isinstance(r, dict)
            else (getattr(r, "deleted_reason", None) or "")[:19],
        )
    console.print(table)
    if stats.get("expiring_soon", 0) > 0:
        console.print(
            f"[yellow]{stats['expiring_soon']} item(s) expiring within 7 days[/yellow]"
        )


@app.command("auto-purge")
def cmd_auto_purge(
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Show what would be purged without deleting"
    ),
):
    """Auto-purge expired trashed resources based on auto_purge_days setting."""
    config = db.get_pool_config()
    if config.get("auto_purge_enabled") != "true":
        console.print("[yellow]Auto-purge is disabled. Enable it in Settings.[/yellow]")
        return
    ids = []
    with db.get_conn() as conn:
        rows = conn.execute(
            """SELECT id, title, deleted_at FROM resources
               WHERE deleted_at IS NOT NULL
               AND trash_expires_at IS NOT NULL
               AND trash_expires_at < datetime('now')"""
        ).fetchall()
        ids = [dict(r) for r in rows]
    if not ids:
        console.print("[green]No expired resources to purge.[/green]")
        return
    console.print(f"[bold]Found {len(ids)} expired resource(s) to purge:[/bold]")
    for r in ids:
        console.print(
            f"  [{r['id']}] {r['title'][:50]} (deleted: {(r['deleted_at'] or '')[:10]})"
        )
    if dry_run:
        console.print("[yellow]DRY RUN — nothing purged.[/yellow]")
        return
    confirmed = typer.confirm(f"Purge all {len(ids)} expired resources?")
    if not confirmed:
        console.print("[yellow]Cancelled.[/yellow]")
        return
    result = db.purge_expired_trash()
    console.print(f"[green]Purged {result['purged']} expired resource(s).[/green]")


@app.command("nuke")
def cmd_nuke():
    """Permanently delete ALL trashed resources."""
    count = db.get_trash_count()
    if count == 0:
        console.print("[yellow]Trash is empty. Nothing to nuke.[/yellow]")
        return
    console.print(
        f"[bold red]NUKE: {count} trashed resource(s) will be PERMANENTLY DELETED.[/bold red]"
    )
    console.print(
        "[red]This cannot be undone. A backup will be created automatically.[/red]"
    )
    phrase = typer.prompt('Type "NUKE" to confirm')
    if phrase != "NUKE":
        console.print("[yellow]Nuke cancelled.[/yellow]")
        return
    ids = []
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM resources WHERE deleted_at IS NOT NULL"
        ).fetchall()
        ids = [r["id"] for r in rows]
    if not ids:
        console.print("[yellow]Nothing to nuke.[/yellow]")
        return
    from app.api.trash import _backup_before_purge

    backup_path = _backup_before_purge(ids, label="nuke")
    result = db.purge_resources(ids)
    for rid in ids:
        try:
            delete_note_by_id(rid)
        except Exception:
            pass
    console.print(f"[green]Nuked {result['purged']} resource(s).[/green]")
    console.print(f"[dim]Backup saved: {backup_path}[/dim]")


@app.command("use")
def cmd_use(
    resource_id: str = typer.Argument(...),
):
    """Mark a resource as used (increments counter)."""
    db.increment_used(resource_id)
    console.print(f"[green]Usage recorded for {resource_id}[/green]")


@app.command("path")
def cmd_path(
    goal: str = typer.Argument(...),
):
    """Generate a learning path from your pool."""
    from app.freellm_tasks import generate_learning_path

    console.print(f"[bold]Generating learning path for: {goal}[/bold]\n")
    all_resources = db.get_all_resources(limit=200)
    pool_data = [
        {
            "id": r.id,
            "title": r.title,
            "domain": r.domain,
            "skill_level": r.skill_level,
            "time_to_value": r.time_to_value,
            "type": r.type,
        }
        for r in all_resources
    ]
    with console.status("[bold green]AI generating path...[/bold green]"):
        result = generate_learning_path(goal=goal, pool_resources=pool_data)
    if not result:
        console.print("[red]Failed to generate path. Is AI enabled?[/red]")
        return
    path_name = result.get("path_name", goal)
    console.print(f"\n[bold]{path_name}[/bold]\n")
    for week in result.get("weeks", []):
        console.print(f"[bold yellow]{week.get('label', 'Week')}[/bold yellow]")
        for item in week.get("resources", []):
            console.print(
                f"  - [{item.get('id', '??')}] {item.get('title', 'Unknown')}"
            )
            if item.get("rationale"):
                console.print(f"    [dim]{item['rationale']}[/dim]")
        console.print()


@app.command("stack")
def cmd_stack(
    mission: str = typer.Argument(...),
):
    """Generate a resource bundle for a specific mission."""
    from app.freellm_tasks import generate_stack

    all_resources = db.get_all_resources(limit=200)
    pool_data = [
        {"id": r.id, "title": r.title, "domain": r.domain, "type": r.type}
        for r in all_resources
    ]
    with console.status("[bold green]AI building stack...[/bold green]"):
        result = generate_stack(mission=mission, pool_resources=pool_data)
    if not result:
        console.print("[red]Failed to generate stack.[/red]")
        return
    console.print(f"\n[bold]Stack: {result.get('stack_name', mission)}[/bold]")
    console.print(f"[dim]{result.get('description', '')}[/dim]\n")
    for item in result.get("resources", []):
        console.print(f"  [{item.get('id', '??')}] {item.get('title', 'Unknown')}")
        if item.get("role"):
            console.print(f"    [dim]Role: {item['role']}[/dim]")


@app.command("gap")
def cmd_gap(
    report: bool = typer.Option(
        False, "--report", "-r", help="Generate detailed gap report"
    ),
):
    """Identify gaps in your resource pool."""
    if report:
        with console.status(
            "[bold green]Generating detailed gap report...[/bold green]"
        ):
            gap_report = run_gap_report()
        if not gap_report:
            console.print(
                "[yellow]Gap report unavailable (AI may be disabled)[/yellow]"
            )
            return
        console.print(f"\n[bold]Gap Analysis Report[/bold]\n")
        console.print(f"{gap_report.get('executive_summary', '')}\n")
        health = gap_report.get("pool_health_score", "?")
        console.print(f"Pool Health Score: [bold]{health}/100[/bold]\n")
        coverage = gap_report.get("domain_coverage", {})
        if coverage.get("coverage"):
            console.print("[bold]Domain Coverage:[/bold]")
            for d in coverage["coverage"]:
                status_color = {
                    "underserved": "red",
                    "adequate": "yellow",
                    "well_covered": "green",
                }.get(d.get("status", ""), "white")
                console.print(
                    f"  [{status_color}]{d['domain']:15s}[/{status_color}] "
                    f"{d['count']:3d}  {d.get('note', '')}"
                )
            console.print()
        types = gap_report.get("type_breakdown", {})
        if types.get("missing_types"):
            console.print(
                f"[yellow]Missing types:[/yellow] {', '.join(types['missing_types'])}"
            )
        skills = gap_report.get("skill_levels", {})
        if skills.get("breakdown"):
            b = skills["breakdown"]
            console.print(
                f"\n[bold]Skill Levels:[/bold] "
                f"Beginner: {b.get('beginner', 0)}, "
                f"Intermediate: {b.get('intermediate', 0)}, "
                f"Advanced: {b.get('advanced', 0)}"
            )
            if skills.get("gap"):
                console.print(f"  [dim]{skills['gap']}[/dim]")
        console.print(f"\n[bold]Priority Recommendations:[/bold]")
        for rec in gap_report.get("priority_recommendations", []):
            p_color = {"high": "red", "medium": "yellow", "low": "dim"}.get(
                rec.get("priority", "low"), "white"
            )
            console.print(
                f"  [{p_color}][{rec.get('priority', 'low').upper()}][/{p_color}] "
                f"{rec.get('action', '')}"
            )
            if rec.get("expected_impact"):
                console.print(f"       [dim]Impact: {rec['expected_impact']}[/dim]")
        return
    with console.status("[bold green]Running gap analysis...[/bold green]"):
        result = full_audit()
    gaps = result.get("gaps")
    if gaps:
        console.print("\n[bold]Pool Gaps:[/bold]\n")
        for gap in gaps.get("gaps", []):
            console.print(
                f"  [yellow][/yellow] {gap.get('domain', '')}: {gap.get('issue', '')}"
            )
            console.print(f"    [dim]-> {gap.get('suggestion', '')}[/dim]")
        console.print(
            "\n[dim]Tip: run [bold]pool gap --report[/bold] for detailed report[/dim]"
        )
    else:
        console.print("[yellow]Gap analysis unavailable (AI may be disabled)[/yellow]")


@app.command("brief")
def cmd_brief():
    """Generate daily briefing of pool activity and recommendations."""
    from app.freellm_tasks import generate_briefing
    from app.search import get_recent, get_untouched
    from datetime import datetime, timedelta

    with console.status("[bold green]Generating daily briefing...[/bold green]"):
        stats = db.get_pool_stats()
        recent = [r.to_dict() for r in get_recent(limit=10)]
        due = {
            "untouched": len(get_untouched(limit=50)),
            "stale": len(db.get_stale_resources(days=90)),
        }
        result = generate_briefing(stats, recent, due)

    if not result:
        console.print("[yellow]Briefing unavailable (AI may be disabled)[/yellow]")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    console.print(f"\n[bold]Daily Briefing - {today}[/bold]\n")
    console.print(f"{result.get('summary', 'No summary')}\n")

    new_count = result.get("new_today", 0)
    due_count = result.get("items_due", 0)
    stale_count = result.get("stale_count", 0)
    dead_count = result.get("dead_links_found", 0)
    console.print(
        f"  [green]+{new_count} new[/green]  "
        f"[yellow]{due_count} due[/yellow]  "
        f"[red]{stale_count} stale[/red]  "
        f"[dim]{dead_count} dead links[/dim]"
    )

    focus = result.get("recommended_focus")
    if focus:
        console.print(f"\n[bold]Focus today:[/bold] {focus}")

    gem = result.get("random_gem", {})
    if gem and gem.get("id"):
        console.print(f"\n[bold]Random gem:[/bold] [{gem['id']}] {gem['title']}")
        console.print(f"  [dim]{gem.get('reason', '')}[/dim]")

    tip = result.get("tip")
    if tip:
        console.print(f"\n[bold]Tip:[/bold] {tip}")


@app.command("graph")
def cmd_graph(
    format_: str = typer.Option(
        "d3", "--format", "-f", help="Output format: d3 (HTML) or obsidian (wiki-links)"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output path (default: poolmind-graph.html for d3)"
    ),
    min_weight: int = typer.Option(
        1, "--min-weight", "-w", help="Minimum edge weight to include"
    ),
):
    """Export resource relationship graph."""
    from app.graph import build_graph_data, export_d3_html, export_obsidian_links

    with console.status("[bold green]Building graph data..."):
        graph_data = build_graph_data(min_edge_weight=min_weight)

    if not graph_data["nodes"]:
        console.print("[yellow]No resources to graph.[/yellow]")
        return

    console.print(
        f"[dim]Graph: {graph_data['node_count']} nodes, {graph_data['edge_count']} edges[/dim]"
    )

    if format_ == "obsidian":
        with console.status("[bold green]Updating Obsidian notes..."):
            stats = export_obsidian_links(graph_data)
        console.print(
            f"[green]Obsidian graph updated:[/green]\n"
            f"  Notes updated: {stats['notes_updated']}\n"
            f"  Links added: {stats['links_added']}\n"
            f"  Hub index: {'written' if stats['hub_written'] else 'failed'}"
        )
        console.print(
            "[dim]Open Obsidian and check Graph View to see the connections.[/dim]"
        )

    else:
        out_path = output or "poolmind-graph.html"
        with console.status("[bold green]Generating D3.js graph..."):
            export_d3_html(graph_data, output_path=out_path)
        console.print(f"[green]D3 graph written:[/green] {out_path}")
        console.print("[dim]Open in a browser to explore the resource graph.[/dim]")


@app.command("dedupe")
def cmd_dedupe(
    threshold: int = typer.Option(
        85, "--threshold", "-t", help="Match threshold (0-100)"
    ),
):
    """Find duplicate resources in the pool."""
    with console.status("[bold green]Scanning for duplicates...[/bold green]"):
        dupes = find_all_duplicates(threshold=threshold)
    if not dupes:
        console.print("[green]No duplicates found.[/green]")
        return
    console.print(f"\n[bold]Found {len(dupes)} potential duplicate(s):[/bold]\n")
    for d in dupes:
        a = d["resource_a"]
        b = d["resource_b"]
        console.print(
            f"[yellow]Match {d['score']}%[/yellow] "
            f"[{a['id']}] {a['title'][:50]} <-> [{b['id']}] {b['title'][:50]}"
        )


@app.command("due")
def cmd_due(
    limit: int = typer.Option(20, "--limit", "-l", help="Max results"),
):
    """Resources due for review (stale, unverified, untouched for a while)."""
    stale = db.get_stale_resources(days=90)
    untouched = get_untouched(limit=limit)

    console.print(f"[bold]Pool Review Due[/bold]\n")

    console.print(f"[yellow]Stale ({len(stale)} not verified in 90+ days):[/yellow]")
    for r in stale[:5]:
        console.print(
            f"  [{r.id}] {r.title[:60]} - last verified: {r.last_verified_alive or 'never'}"
        )

    if len(stale) > 5:
        console.print(f"  [dim]... and {len(stale) - 5} more[/dim]")

    console.print(
        f"\n[cyan]Untouched ({len(untouched)} still in 'saved' state):[/cyan]"
    )
    for r in untouched[:5]:
        console.print(
            f"  [{r.id}] {r.title[:60]} - {r.domain} | {r.type} | added {r.added_on}"
        )

    if len(untouched) > 5:
        console.print(f"  [dim]... and {len(untouched) - 5} more[/dim]")

    low_conf = get_low_confidence_resources(threshold=70)
    if low_conf:
        console.print(
            f"\n[yellow]Low AI confidence ({len(low_conf)} need human review):[/yellow]"
        )
        for r in low_conf[:5]:
            console.print(f"  [{r.id}] {r.title[:60]} - confidence: {r.ai_confidence}%")

    console.print(f"\n[dim]Run [bold]pool audit[/bold] for full report[/dim]")


@app.command("progress")
def cmd_progress():
    """Show learning progress breakdown."""
    stats = db.get_pool_stats()

    console.print(f"[bold]Learning Progress[/bold]\n")

    total = stats["total"]
    by_state = {s["consumption_state"]: s["c"] for s in stats["by_state"]}

    saved = by_state.get("saved", 0)
    skimmed = by_state.get("skimmed", 0)
    studied = by_state.get("studied", 0)
    mastered = by_state.get("mastered", 0)
    applied = by_state.get("applied", 0)
    archived = by_state.get("archived", 0)

    consumed = skimmed + studied + mastered + applied
    pct_consumed = round(consumed / total * 100) if total > 0 else 0

    bar_width = 30
    filled = round(pct_consumed / 100 * bar_width)
    bar = "#" * filled + "-" * (bar_width - filled)

    console.print(f"  [{bar}]  {pct_consumed}% consumed ({consumed}/{total})\n")

    state_colors = {
        "saved": "dim",
        "skimmed": "cyan",
        "studied": "yellow",
        "mastered": "green",
        "applied": "bright_green",
        "archived": "red",
    }
    for state in ("saved", "skimmed", "studied", "mastered", "applied", "archived"):
        count = by_state.get(state, 0)
        pct = round(count / total * 100) if total > 0 else 0
        color = state_colors.get(state, "white")
        state_display = state.replace("_", " ").title()
        console.print(f"  [{color}]* {state_display}: {count} ({pct}%)[/{color}]")

    console.print(f"\n[bold]By Domain:[/bold]")
    for d in stats["by_domain"][:8]:
        domain_pct = round(d["c"] / total * 100) if total > 0 else 0
        domain_bar = "#" * max(1, domain_pct // 5)
        console.print(
            f"  [blue]{d['domain']:15s}[/blue] {domain_bar} {d['c']} ({domain_pct}%)"
        )

    dead = stats.get("dead_links", 0)
    if dead:
        console.print(
            f"\n[red]! {dead} dead link(s) - run [bold]pool dead-check[/bold][/red]"
        )


@app.command("dead-check")
def cmd_dead_check(
    limit: int = typer.Option(50, "--limit", "-l"),
    auto_tombstone: bool = typer.Option(
        False, "--auto-tombstone", "-t", help="Archive confirmed dead resources"
    ),
):
    """Check for dead/broken links."""
    console.print(f"[bold]Checking up to {limit} stale links...[/bold]\n")
    with console.status("[bold green]Checking links...[/bold green]"):
        results = dead_check(limit=limit, auto_tombstone=auto_tombstone)

    console.print(f"[green][OK] Alive: {results['alive']}[/green]")
    console.print(f"[red][DEAD] Dead: {len(results['dead'])}[/red]")
    if results.get("tombstoned"):
        console.print(f"[yellow][X] Tombstoned: {len(results['tombstoned'])}[/yellow]")
    console.print(f"[dim][SKIP] Skipped (local): {results['skipped']}[/dim]")

    if results["dead"]:
        console.print("\n[bold]Dead links:[/bold]")
        for d in results["dead"]:
            tombstone_mark = (
                " [yellow][X][/yellow]" if d in results.get("tombstoned", []) else ""
            )
            console.print(f"  [{d['id']}] {d['title'][:50]}{tombstone_mark}")
            console.print(f"    [red]{d['url']}[/red] (HTTP {d['status']})")
            if d.get("wayback"):
                console.print(f"    [dim]Wayback: {d['wayback']}[/dim]")


@app.command("audit")
def cmd_audit():
    """Run full pool audit (stats, gaps, dead links, low confidence)."""
    with console.status("[bold green]Running full audit...[/bold green]"):
        result = full_audit()
    stats = result["stats"]
    console.print(f"\n[bold]Pool Audit Report[/bold]\n")
    console.print(f"Total resources: [bold]{stats['total']}[/bold]")
    console.print(f"Dead links: [red]{stats['dead_links']}[/red]")
    console.print(f"Low confidence: [yellow]{stats['low_confidence']}[/yellow]")
    console.print(f"Stale content: [yellow]{result['stale_content_count']}[/yellow]")
    console.print("\n[bold]Top Domains:[/bold]")
    for d in stats["by_domain"][:5]:
        console.print(f"  {d['domain']}: {d['c']}")
    console.print("\n[bold]Consumption States:[/bold]")
    for s in stats["by_state"]:
        console.print(f"  {s['consumption_state']}: {s['c']}")


@app.command("stats")
def cmd_stats():
    """Show pool statistics."""
    stats = db.get_pool_stats()
    console.print(f"\n[bold]Pool Statistics[/bold]\n")
    console.print(f"[bold]{stats['total']}[/bold] resources\n")
    table = Table(title="By Domain", show_header=True)
    table.add_column("Domain")
    table.add_column("Count", justify="right")
    for d in stats["by_domain"][:10]:
        table.add_row(d["domain"], str(d["c"]))
    console.print(table)


@app.command("watch")
def cmd_watch(
    interval: int = typer.Option(
        24, "--interval", "-i", help="Hours between maintenance runs"
    ),
    auto_tombstone: bool = typer.Option(
        False, "--auto-tombstone", "-t", help="Auto-archive dead resources"
    ),
):
    """Start continuous pool maintenance (dead check, audit, etc.)."""
    console.print(
        f"[bold green][WATCH] watch mode started[/bold green] (interval: {interval}h, auto-tombstone: {auto_tombstone})"
    )
    console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

    from scripts.scheduler import watch_loop

    try:
        watch_loop(interval_hours=interval, auto_tombstone=auto_tombstone)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch mode stopped.[/yellow]")


@app.command("serve")
def cmd_serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    port: int = typer.Option(5000, "--port", "-p", help="Port number"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Debug mode"),
):
    """Start the poolmind web UI."""
    from app.webui import run_server

    run_server(host=host, port=port, debug=debug)


@app.command("anki")
def cmd_anki(
    output: str = typer.Option(
        "poolmind-anki.csv", "--output", "-o", help="Output CSV path"
    ),
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Domain filter"),
    type_: Optional[str] = typer.Option(None, "--type", "-t", help="Type filter"),
    limit: int = typer.Option(200, "--limit", "-l", help="Max resources"),
):
    """Export resources as Anki-importable CSV."""
    from app.anki import export_csv

    with console.status("[bold green]Generating Anki deck..."):
        result = export_csv(output_path=output, domain=domain, type_=type_, limit=limit)
    console.print(
        f"[green]Anki CSV written:[/green] {result['path']} ({result['cards']} cards)"
    )
    console.print(
        "[dim]Import in Anki: File > Import > select CSV > set delimiter to comma[/dim]"
    )


@app.command("site")
def cmd_site(
    output: str = typer.Option(
        "poolmind-site.html", "--output", "-o", help="Output HTML path"
    ),
):
    """Generate a static HTML site from the resource pool."""
    from app.sitegen import generate_site

    with console.status("[bold green]Generating static site..."):
        result = generate_site(output_path=output)
    console.print(
        f"[green]Static site written:[/green] {result['path']} ({result['resources']} resources)"
    )
    console.print("[dim]Open in a browser to view.[/dim]")


@app.command("sync-notion")
def cmd_sync_notion(
    batch: int = typer.Option(10, "--batch", "-b", help="Batch size"),
):
    """Sync pending resources to Notion."""
    from app.notion_sync import sync_all_pending

    with console.status("[bold green]Syncing to Notion...[/bold green]"):
        result = sync_all_pending(batch_size=batch)
    console.print(f"[green]Synced: {result['synced']}[/green]")
    if result["failed"]:
        console.print(f"[red]Failed: {result['failed']}[/red]")


@app.command("prompt-stats")
def cmd_prompt_stats(
    task: Optional[str] = typer.Option(
        None, "--task", "-t", help="Task name (default: all)"
    ),
    last_n: int = typer.Option(50, "--last-n", "-n", help="Last N calls to analyze"),
):
    """Show AI prompt performance stats per task."""
    if task:
        from app.feedback_tracker import get_task_stats

        stats = [get_task_stats(task, last_n=last_n)]
    else:
        stats = get_all_task_stats(last_n=last_n)

    if not stats:
        console.print("[yellow]No feedback data yet.[/yellow]")
        return

    table = Table(
        title=f"Prompt Performance Stats (last {last_n} calls each)",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Task")
    table.add_column("Calls", justify="right")
    table.add_column("Success", justify="right")
    table.add_column("Coverage", justify="right")
    table.add_column("Confidence", justify="right")
    table.add_column("Corrections", justify="right")
    table.add_column("Health")

    for s in stats:
        task_name = s["task"]
        total = s["total_calls"]
        success = (
            f"{s['success_rate'] * 100:.0f}%" if s["success_rate"] is not None else "-"
        )
        coverage = (
            f"{s['avg_field_coverage'] * 100:.0f}%"
            if s["avg_field_coverage"] is not None
            else "-"
        )
        conf = f"{s['avg_confidence']:.0f}" if s["avg_confidence"] is not None else "-"
        corr = (
            f"{s['user_correction_rate'] * 100:.0f}%"
            if s["user_correction_rate"] is not None
            else "-"
        )

        if s["needs_evolution"]:
            health = "[red]needs evolution[/red]"
        elif "insufficient_data" in (s.get("reason") or ""):
            health = "[dim]insufficient data[/dim]"
        else:
            health = "[green]healthy[/green]"

        table.add_row(task_name, str(total), success, coverage, conf, corr, health)

    console.print(table)
    console.print(
        "[dim]Run 'pool evolve --dry-run' to preview prompt improvements[/dim]"
    )


@app.command("evolve")
def cmd_evolve(
    task: Optional[str] = typer.Option(
        None, "--task", "-t", help="Task to evolve (default: all)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Preview only, no changes"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force evolution even if healthy"
    ),
    last_n: int = typer.Option(
        50, "--last-n", help="Last N feedback samples to analyze"
    ),
):
    """Evolve AI prompts based on observed performance."""
    if task:
        results = [
            evolve_prompt(
                task=task, force=force, dry_run=dry_run, last_n_feedback=last_n
            )
        ]
    else:
        results = evolve_all(force=force, dry_run=dry_run, last_n_feedback=last_n)

    evolved = [r for r in results if r["evolved"]]
    skipped = [r for r in results if not r["evolved"]]

    if dry_run:
        console.print(f"\n[bold]Dry Run Results[/bold]\n")
    else:
        console.print(f"\n[bold]Evolution Results[/bold]\n")

    if evolved:
        for r in evolved:
            if dry_run:
                console.print(
                    f"[green]Would evolve:[/green] {r['task']} ({r['reason']})"
                )
                console.print(f"  [dim]{r.get('diff_summary', '')}[/dim]")
                if r.get("improved_prompt"):
                    console.print(
                        f"  [dim]Preview: {r['improved_prompt'][:120]}...[/dim]"
                    )
            else:
                console.print(f"[green]Evolved:[/green] {r['task']} ({r['reason']})")
                console.print(f"  [dim]Backup: {r.get('backup_path', 'N/A')}[/dim]")
                console.print(f"  [dim]{r.get('diff_summary', '')}[/dim]")
        console.print()

    if skipped:
        for r in skipped:
            reason = r.get("reason", "unknown")
            if "healthy" in reason:
                console.print(f"  [dim]Skipped (healthy): {r['task']}[/dim]")
            elif "insufficient_data" in reason:
                console.print(f"  [dim]Skipped (insufficient data): {r['task']}[/dim]")
            else:
                console.print(f"  [yellow]Skipped: {r['task']} ({reason})[/yellow]")

    if not evolved and not skipped:
        console.print("[yellow]No results.[/yellow]")


@app.command("correct")
def cmd_correct(
    resource_id: str = typer.Argument(..., help="Resource ID"),
    field: str = typer.Argument(..., help="Field name that was wrong"),
    old_value: str = typer.Argument(..., help="Incorrect AI value"),
    new_value: str = typer.Argument(..., help="Correct value"),
):
    """Record a user correction against AI output for a resource."""
    resource = db.get_resource(resource_id)
    if not resource:
        console.print(f"[red]Resource not found: {resource_id}[/red]")
        raise typer.Exit(1)

    db.update_resource(resource_id, {field: new_value})

    task = _map_field_to_task(field)
    input_content = json.dumps(
        {"resource_id": resource_id, "field": field, "old": old_value}
    )
    log_user_correction(task, input_content, f"{field}: {old_value} -> {new_value}")

    console.print(f"[green]Correction recorded for {resource_id}.{field}[/green]")


@app.command("prompt-history")
def cmd_prompt_history(
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Filter by task"),
):
    """Show prompt evolution history and available backups."""
    evolutions = get_evolution_history(task=task)
    if evolutions:
        table = Table(
            title="Prompt Evolution History", show_header=True, header_style="bold cyan"
        )
        table.add_column("Date")
        table.add_column("Task")
        table.add_column("Old Ver")
        table.add_column("New Ver")
        table.add_column("Trigger")
        table.add_column("Backup")
        for e in evolutions:
            table.add_row(
                (e.get("created_at") or "")[:16],
                e.get("task", ""),
                (e.get("old_prompt_version") or "")[:8],
                (e.get("new_prompt_version") or "")[:8],
                (e.get("trigger_reason") or "")[:20],
                (e.get("backup_path") or "")[:40],
            )
        console.print(table)
    else:
        console.print("[yellow]No evolution history yet.[/yellow]")

    if task:
        backups = list_backups(task)
        if backups:
            console.print(f"\n[bold]Available backups for '{task}':[/bold]")
            for b in backups:
                console.print(
                    f"  {b['filename']}  ({b['size_bytes']} bytes, {b['created'][:16]})"
                )
        else:
            console.print(f"\n[dim]No backups for '{task}'.[/dim]")


@app.command("prompt-restore")
def cmd_prompt_restore(
    task: str = typer.Argument(..., help="Task name"),
    version: Optional[str] = typer.Option(
        None, "--version", "-v", help="Backup filename or timestamp to restore from"
    ),
):
    """Restore a prompt from a backup version."""
    if not version:
        backups = list_backups(task)
        if not backups:
            console.print(f"[red]No backups found for '{task}'.[/red]")
            raise typer.Exit(1)
        console.print(f"[bold]Backups for '{task}':[/bold]")
        for b in backups:
            console.print(f"  {b['filename']}")
        console.print("[dim]Use --version to specify which to restore.[/dim]")
        return

    success = restore_prompt(task, version_timestamp=version)
    if success:
        console.print(f"[green]Prompt '{task}' restored from {version}[/green]")
    else:
        console.print(
            f"[red]Restore failed. Version '{version}' not found for '{task}'.[/red]"
        )
        raise typer.Exit(1)


def _map_field_to_task(field: str) -> str:
    """Map a resource field to its AI task name for feedback tracking."""
    field_to_task = {
        "type": "classify_resource",
        "domain": "classify_resource",
        "subdomain": "classify_resource",
        "skill_level": "classify_resource",
        "format": "classify_resource",
        "time_to_value": "classify_resource",
        "cost": "classify_resource",
        "summary": "summarize_resource",
        "why_it_matters": "summarize_resource",
        "best_for": "summarize_resource",
        "avoid_if": "summarize_resource",
        "quality_score": "summarize_resource",
        "tags": "generate_tags",
        "notes": "improve_note",
    }
    return field_to_task.get(field, "classify_resource")


def _print_resource_card(resource: Resource, action: str = "Found"):
    quality = f"{resource.quality_score}/10" if resource.quality_score else "?"
    confidence = f"{resource.ai_confidence}%" if resource.ai_confidence else "N/A"
    tags_str = " ".join(f"#{t}" for t in resource.tags[:8]) if resource.tags else ""
    console.print(
        Panel(
            f"[bold]{resource.title}[/bold]\n"
            f"[dim]{resource.url[:80]}[/dim]\n\n"
            f"Type: [cyan]{resource.type}[/cyan] | "
            f"Domain: [blue]{resource.domain}[/blue] | "
            f"Level: {resource.skill_level} | "
            f"Time: {resource.time_to_value} | "
            f"Cost: {resource.cost}\n\n"
            f"Quality: {quality} | AI Confidence: {confidence}\n"
            f"Tags: {tags_str}\n\n"
            f"{resource.summary or 'No summary yet.'}\n"
            f"[dim]ID: {resource.id}[/dim]",
            title=f"[green]{action}[/green]",
            border_style="green",
        )
    )


def _print_search_card(index: int, resource: Resource):
    quality = f"{resource.quality_score}/10" if resource.quality_score else "?"
    relevance = (
        f" | Relevance: {resource.relevance_score}%" if resource.relevance_score else ""
    )
    console.print(
        f"[bold]{index}.[/bold] [{resource.id}] [bold]{resource.title[:70]}[/bold]\n"
        f"   [dim]{resource.domain} | {resource.type} | {resource.skill_level} | {resource.time_to_value}{relevance}[/dim]\n"
        f"   [cyan]{resource.url[:80]}[/cyan]\n"
        f"   {resource.summary[:120] + '...' if resource.summary and len(resource.summary) > 120 else resource.summary or ''}\n"
        f"   Quality: {quality}\n"
    )


def _print_resource_full(resource: Resource):
    _print_resource_card(resource, action="Resource")
    if resource.why_it_matters:
        console.print(f"[bold]Why it matters:[/bold] {resource.why_it_matters}")
    if resource.best_for:
        console.print(f"[bold]Best for:[/bold] {resource.best_for}")
    if resource.avoid_if:
        console.print(f"[bold]Avoid if:[/bold] {resource.avoid_if}")
    if resource.prerequisites:
        console.print(
            f"[bold]Prerequisites:[/bold] {', '.join(resource.prerequisites)}"
        )
    if resource.notes:
        console.print(f"[bold]Notes:[/bold] {resource.notes}")
    if resource.mirror_urls:
        console.print(f"[bold]Mirrors:[/bold] {', '.join(resource.mirror_urls)}")


def _print_results_table(resources: list):
    if not resources:
        console.print("[yellow]No resources found.[/yellow]")
        return
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", width=10)
    table.add_column("Title", width=45)
    table.add_column("Domain", width=15)
    table.add_column("Type", width=12)
    table.add_column("Level", width=12)
    table.add_column("Q", width=4, justify="right")
    table.add_column("State", width=12)
    for r in resources:
        table.add_row(
            r.id,
            r.title[:44],
            r.domain,
            r.type,
            r.skill_level,
            str(r.quality_score) if r.quality_score else "-",
            r.consumption_state,
        )
    console.print(table)


def main():
    app()


if __name__ == "__main__":
    main()
