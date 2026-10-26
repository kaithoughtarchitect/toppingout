# Skills wiki

Mirror graph of the **runnable** skills in `skills/` and the agents in `agents/`.

**Folders run. This wiki maps.** Cold start: `[[index]]`. The process: `../METHOD.md`. The flow: `../flow.html`.

A skill is not done until `skills/<name>/SKILL.md` **and** `skills-wiki/<name>.md` exist. Agents live in `skills-wiki/agents/`.

```
python scripts/wiki_lint.py skills-wiki
python scripts/wiki_graph_html.py skills-wiki "Topping Out Skill Atlas"
python scripts/skills_wiki_sync.py .
```
