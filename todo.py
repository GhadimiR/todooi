#!/usr/bin/env python3
"""Fast, minimal TUI todo list with Azure sync."""

import sys
import os
import tty
import termios
from storage import TodoStorage

# ANSI escape codes
CLEAR = "\033[2J\033[H"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
STRIKE = "\033[9m"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


def getch():
    """Get a single character from stdin."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Handle escape sequences (arrows)
        if ch == '\x1b':
            ch2 = sys.stdin.read(1)
            if ch2 == '[':
                ch3 = sys.stdin.read(1)
                return {'A': 'up', 'B': 'down', 'C': 'right', 'D': 'left'}.get(ch3, '')
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def readline_raw(prompt: str) -> str:
    """Read a line with backspace support in raw mode."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        sys.stdout.write(prompt)
        sys.stdout.flush()
        buf = []
        while True:
            ch = sys.stdin.read(1)
            if ch in ('\r', '\n'):
                sys.stdout.write('\r\n')
                break
            elif ch == '\x7f':  # backspace
                if buf:
                    buf.pop()
                    sys.stdout.write('\b \b')
            elif ch == '\x03':  # Ctrl+C
                return ''
            elif ch == '\x1b':  # Escape
                return ''
            elif ch >= ' ':
                buf.append(ch)
                sys.stdout.write(ch)
            sys.stdout.flush()
        return ''.join(buf)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


class TodoApp:
    def __init__(self):
        self.storage = TodoStorage()
        self.lists: list[dict] = []
        self.items: list[dict] = []
        self.current_list_idx = 0
        self.cursor = 0
        self.message = ""
        self.mode = "list"  # "list" or "notes"
        self.notes_buffer: list[str] = []
        self.notes_cursor_line = 0
        self.notes_cursor_col = 0
        self.load_lists()

    def load_lists(self):
        self.lists = self.storage.get_lists()
        if self.lists:
            self.current_list_idx = min(self.current_list_idx, len(self.lists) - 1)
            self.load_items()
        else:
            self.items = []

    def load_items(self):
        if self.lists:
            self.items = self.storage.get_items(self.lists[self.current_list_idx]["id"])
            self.cursor = min(self.cursor, max(0, len(self.items) - 1))
        else:
            self.items = []
            self.cursor = 0

    @property
    def current_list(self) -> dict | None:
        return self.lists[self.current_list_idx] if self.lists else None

    def render(self):
        if self.mode == "notes":
            self.render_notes()
            return
        self.render_list()

    def render_list(self):
        lines = [CLEAR]
        
        # Header with list tabs
        tabs = []
        for i, lst in enumerate(self.lists):
            if i == self.current_list_idx:
                tabs.append(f"{BOLD}{CYAN}[{lst['name']}]{RESET}")
            else:
                tabs.append(f"{DIM}{lst['name']}{RESET}")
        
        if tabs:
            lines.append("  ".join(tabs) + f"  {DIM}(←/→ switch, N new list){RESET}")
        else:
            lines.append(f"{DIM}No lists. Press N to create one.{RESET}")
        
        lines.append("")
        
        # Items
        if self.current_list and self.items:
            for i, item in enumerate(self.items):
                marker = "›" if i == self.cursor else " "
                if item["done"]:
                    check = f"{GREEN}✓{RESET}"
                    title = f"{DIM}{STRIKE}{item['title']}{RESET}"
                else:
                    check = "○"
                    title = item["title"]
                # Show note indicator
                note_indicator = f" {DIM}📝{RESET}" if item.get("notes") else ""
                lines.append(f" {marker} {check} {title}{note_indicator}")
        elif self.current_list:
            lines.append(f"  {DIM}Empty list. Press 'a' to add a todo.{RESET}")
        
        lines.append("")
        
        # Help
        lines.append(f"{DIM}a{RESET}dd  {DIM}e{RESET}dit  {DIM}d{RESET}elete  {DIM}n{RESET}otes  {DIM}space{RESET}=toggle  {DIM}x{RESET}=clear done  {DIM}N{RESET}ew list  {DIM}q{RESET}uit")
        
        # Message
        if self.message:
            lines.append(f"\n{YELLOW}{self.message}{RESET}")
            self.message = ""
        
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

    def render_notes(self):
        item = self.items[self.cursor]
        lines = [CLEAR]
        
        # Header
        lines.append(f"{BOLD}{CYAN}Notes: {item['title']}{RESET}")
        lines.append(f"{DIM}─" * 50 + RESET)
        lines.append("")
        
        # Notes content with cursor
        for i, line in enumerate(self.notes_buffer):
            if i == self.notes_cursor_line:
                # Show cursor position
                before = line[:self.notes_cursor_col]
                after = line[self.notes_cursor_col:]
                lines.append(f"{before}{BOLD}│{RESET}{after}")
            else:
                lines.append(line)
        
        # If buffer empty or cursor at end
        if not self.notes_buffer:
            lines.append(f"{BOLD}│{RESET}")
        elif self.notes_cursor_line >= len(self.notes_buffer):
            lines.append(f"{BOLD}│{RESET}")
        
        lines.append("")
        lines.append(f"{DIM}─" * 50 + RESET)
        lines.append(f"{DIM}Type to edit • Enter for new line • Esc to save & exit{RESET}")
        
        sys.stdout.write("\n".join(lines))
        sys.stdout.flush()

    def run(self):
        sys.stdout.write(HIDE_CURSOR)
        try:
            while True:
                self.render()
                key = getch()
                
                if self.mode == "notes":
                    self.handle_notes_key(key)
                else:
                    self.handle_list_key(key)
        finally:
            sys.stdout.write(SHOW_CURSOR + "\n")

    def handle_list_key(self, key):
        if key == 'q':
            sys.exit(0)
        elif key in ('left', 'h') and self.lists:
            self.current_list_idx = (self.current_list_idx - 1) % len(self.lists)
            self.cursor = 0
            self.load_items()
        elif key in ('right', 'l') and self.lists:
            self.current_list_idx = (self.current_list_idx + 1) % len(self.lists)
            self.cursor = 0
            self.load_items()
        elif key in ('up', 'k') and self.items:
            self.cursor = max(0, self.cursor - 1)
        elif key in ('down', 'j') and self.items:
            self.cursor = min(len(self.items) - 1, self.cursor + 1)
        elif key == ' ' and self.items:
            self.toggle_item()
        elif key == 'a' and self.current_list:
            self.add_item()
        elif key == 'e' and self.items:
            self.edit_item()
        elif key == 'd' and self.items:
            self.delete_item()
        elif key == 'n' and self.items:
            self.enter_notes()
        elif key == 'N':
            self.new_list()
        elif key == 'R' and self.current_list:
            self.rename_list()
        elif key == 'D' and self.current_list:
            self.delete_list()
        elif key == 'r':
            self.load_lists()
            self.message = "Refreshed"
        elif key == 'x' and self.current_list:
            self.clear_done()

    def handle_notes_key(self, key):
        if key == '\x1b':  # Escape
            self.save_notes()
            self.mode = "list"
            self.load_items()
        elif key == '\r' or key == '\n':  # Enter
            # Split line at cursor and insert new line
            if self.notes_buffer:
                current_line = self.notes_buffer[self.notes_cursor_line]
                before = current_line[:self.notes_cursor_col]
                after = current_line[self.notes_cursor_col:]
                self.notes_buffer[self.notes_cursor_line] = before
                self.notes_buffer.insert(self.notes_cursor_line + 1, after)
            else:
                self.notes_buffer.append("")
            self.notes_cursor_line += 1
            self.notes_cursor_col = 0
        elif key == '\x7f':  # Backspace
            if self.notes_cursor_col > 0:
                line = self.notes_buffer[self.notes_cursor_line]
                self.notes_buffer[self.notes_cursor_line] = line[:self.notes_cursor_col-1] + line[self.notes_cursor_col:]
                self.notes_cursor_col -= 1
            elif self.notes_cursor_line > 0:
                # Join with previous line
                prev_line = self.notes_buffer[self.notes_cursor_line - 1]
                curr_line = self.notes_buffer[self.notes_cursor_line]
                self.notes_buffer[self.notes_cursor_line - 1] = prev_line + curr_line
                del self.notes_buffer[self.notes_cursor_line]
                self.notes_cursor_line -= 1
                self.notes_cursor_col = len(prev_line)
        elif key == 'up':
            if self.notes_cursor_line > 0:
                self.notes_cursor_line -= 1
                self.notes_cursor_col = min(self.notes_cursor_col, len(self.notes_buffer[self.notes_cursor_line]))
        elif key == 'down':
            if self.notes_cursor_line < len(self.notes_buffer) - 1:
                self.notes_cursor_line += 1
                self.notes_cursor_col = min(self.notes_cursor_col, len(self.notes_buffer[self.notes_cursor_line]))
        elif key == 'left':
            if self.notes_cursor_col > 0:
                self.notes_cursor_col -= 1
        elif key == 'right':
            if self.notes_buffer and self.notes_cursor_col < len(self.notes_buffer[self.notes_cursor_line]):
                self.notes_cursor_col += 1
        elif isinstance(key, str) and len(key) == 1 and key >= ' ':
            # Insert character
            if not self.notes_buffer:
                self.notes_buffer = [""]
            line = self.notes_buffer[self.notes_cursor_line]
            self.notes_buffer[self.notes_cursor_line] = line[:self.notes_cursor_col] + key + line[self.notes_cursor_col:]
            self.notes_cursor_col += 1

    def enter_notes(self):
        item = self.items[self.cursor]
        notes = item.get("notes", "")
        self.notes_buffer = notes.split("\n") if notes else [""]
        self.notes_cursor_line = 0
        self.notes_cursor_col = 0
        self.mode = "notes"

    def save_notes(self):
        item = self.items[self.cursor]
        notes = "\n".join(self.notes_buffer).rstrip()
        self.storage.update_item(self.current_list["id"], item["id"], notes=notes)
        self.message = "Notes saved"

    def toggle_item(self):
        item = self.items[self.cursor]
        self.storage.toggle_item(self.current_list["id"], item["id"])
        self.load_items()

    def add_item(self):
        sys.stdout.write(SHOW_CURSOR)
        title = readline_raw(f"\n{BOLD}Add:{RESET} ")
        sys.stdout.write(HIDE_CURSOR)
        if title:
            self.storage.create_item(self.current_list["id"], title)
            self.load_items()
            self.cursor = len(self.items) - 1

    def edit_item(self):
        item = self.items[self.cursor]
        sys.stdout.write(SHOW_CURSOR)
        title = readline_raw(f"\n{BOLD}Edit:{RESET} ")
        sys.stdout.write(HIDE_CURSOR)
        if title:
            self.storage.update_item(self.current_list["id"], item["id"], title=title)
            self.load_items()

    def delete_item(self):
        item = self.items[self.cursor]
        self.storage.delete_item(self.current_list["id"], item["id"])
        self.load_items()
        self.message = "Deleted"

    def new_list(self):
        sys.stdout.write(SHOW_CURSOR)
        name = readline_raw(f"\n{BOLD}New list:{RESET} ")
        sys.stdout.write(HIDE_CURSOR)
        if name:
            self.storage.create_list(name)
            self.load_lists()
            self.current_list_idx = len(self.lists) - 1
            self.cursor = 0
            self.load_items()

    def rename_list(self):
        sys.stdout.write(SHOW_CURSOR)
        name = readline_raw(f"\n{BOLD}Rename to:{RESET} ")
        sys.stdout.write(HIDE_CURSOR)
        if name:
            self.storage.update_list(self.current_list["id"], name)
            self.load_lists()

    def delete_list(self):
        self.storage.delete_list(self.current_list["id"])
        self.current_list_idx = max(0, self.current_list_idx - 1)
        self.load_lists()
        self.message = "List deleted"

    def clear_done(self):
        count = self.storage.clear_done(self.current_list["id"])
        self.load_lists()
        self.load_items()
        self.message = f"Cleared {count} done item{'s' if count != 1 else ''}"


def main():
    try:
        app = TodoApp()
        app.run()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stdout.write(SHOW_CURSOR + "\n")


if __name__ == "__main__":
    main()
