## It's working if

- It copies only what's missing and never overwrites a file the repo already has; only an upgrade replaces a file, and only one unchanged since the last install.
- The repo profile is written from what the repo actually has, and you're asked only what it couldn't find, in one batch.
- Every profile row is filled; a row nothing can answer yet says `not recorded` and why.
- The names files exist, are git-ignored and never empty, and the names check proves itself on this machine.
- The test adapter is proved on two fixtures: only the test failing at head alone is reported.
- It never stages, commits or pushes: it ends with the list of files for your commit.
- It ends with one line: `F-SETUP: READY <profile path>` or `F-SETUP: HALTED <reason>`.

## Common questions

### How do I run it the first time?

In the repo that will hold your records, start a session and say `Read <path to the package>/skills/f-setup/SKILL.md and follow it`. The install copies the skill too, so every later run is just `/f-setup`.

### How do I update later?

Run `/f-setup` again. With a receipt in the repo it upgrades: files you didn't adapt are replaced, files you did are listed for a merge by hand. It refuses while a job is open or an end game is owed.

### What does it ask me?

Only what the repo can't answer: typically the product name, ticket mode, board publish mode, the budgets and the builders' names. Each question offers the answer it found as the default.

### What is the first question?

Whether the product is an AI agent built on LangChain, LangGraph or Deep Agents. A yes adds the Deep Agents add-on: `/deep`, a reference checked against the real `deepagents` code, and LangChain's docs server. A no skips it, and nothing else changes.

### Does it touch my secrets?

It reads the names of keys in `.env` files, never their values, and never prints a value.

### How do I remove Topping Out?

The receipt, `foreman/INSTALL-RECEIPT.txt`, lists every file the package installed. Delete those you haven't adapted, then the receipt. Your records stay yours.
