# TUI Todo List

Minimal, fast terminal todo list synced via Azure Table Storage.

## Setup

```bash
./todo
```

First run prompts for your Azure connection string and saves it locally.

## Keys

**Navigation**
- `←` `→` or `h` `l` — switch lists  
- `↑` `↓` or `j` `k` — move cursor
- `space` — toggle done

**Items**
- `a` — add todo
- `e` — edit todo  
- `d` — delete todo
- `n` — open notes (freeform text)

**Notes view**
- Type freely, Enter for new lines
- Arrow keys to move cursor
- `Esc` — save and exit

**Lists**
- `N` — new list
- `R` — rename list
- `D` — delete list

**Other**
- `r` — refresh from Azure
- `q` — quit
