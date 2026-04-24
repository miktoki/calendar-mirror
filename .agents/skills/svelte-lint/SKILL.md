---
name: svelte-lint
description: "Detects changes touching Svelte files or frontend UI code and runs or suggests Svelte-specific linting (ESLint / svelte-check) for the frontend folder. Use this skill when editing or reviewing changes that touch `**/*.svelte`, `frontend/src/**`, or Svelte/Vite/TS config files. Agents should run lint (no --fix) first, summarize issues, and offer --fix as an optional follow-up requiring approval."
argument-hint: "[target] (optional, e.g. frontend/src or specific files)"
user-invocable: true
disable-model-invocation: false
---

# Workspace Svelte Lint Skill

## Overview
This skill helps agents detect and handle Svelte-specific linting when source changes touch Svelte or front-end UI code. The skill runs linters (preferably ESLint configured for Svelte) without auto-fixing by default, summarizes problems, and optionally suggests or runs `--fix` only with explicit permission.

## When to use
- Use ad-hoc during code reviews or while making edits that include any of:
  - `**/*.svelte`
  - `frontend/src/**`
  - `svelte.config.*`, `vite.config.*`, `tsconfig.*`

## Behavior / Steps for agents
1. Detect changed or targeted files. If none match Svelte/UI patterns above, do not run the skill.
2. Inspect `frontend/package.json` for scripts: prefer `lint:svelte`, then `lint`, then `check`.
3. Determine package manager: prefer `pnpm`, then `npm`, then `bun` (use `--prefix frontend` or equivalent).
4. Run the linter without `--fix` first. Example commands:
   - `pnpm --prefix frontend run lint:svelte`
   - `pnpm --prefix frontend dlx eslint --ext .svelte,.ts frontend/src`
   - `npm --prefix frontend run lint`
   - `npx eslint --ext .svelte,.ts frontend/src`
5. Parse lint output and summarize up to 20 unique issues. For each file, return the top message with `file:line:col — message`.
6. If the linter errors due to missing parser/plugin/config, suggest the exact `devDependencies` to add and a minimal `.eslintrc` or `package.json` snippet.
7. Offer `--fix` as an optional follow-up only after summarizing issues. Do not auto-apply fixes or commit without explicit permission.
8. If user/agent authorizes `--fix`, run with `--fix`, then show a concise git diff summary (files changed and number of insertions/deletions).

## Safety and policies
- Do not install packages, modify files, or commit/push changes without explicit user approval.
- Keep outputs concise and actionable: include the exact command run and its exit code, then a short list of files with errors.

## Examples
- Preferred ESLint run (no fix):

  pnpm --prefix frontend dlx eslint --ext .svelte,.ts frontend/src

- To auto-fix after approval:

  pnpm --prefix frontend dlx eslint --ext .svelte,.ts frontend/src --fix

## Suggested `frontend/package.json` additions

```json
"scripts": {
  "lint:svelte": "eslint --ext .svelte,.ts src"
}
```

Dev dependencies commonly required:
- `eslint`
- `@typescript-eslint/parser`
- `@typescript-eslint/eslint-plugin`
- `eslint-plugin-svelte` or `eslint-plugin-svelte3`

## Agent output format (concise)
- Command run and exit code
- Top 20 unique issues as `file:line:col — message`
- If approved, `--fix` summary and git diff stats

---

For maintainers: place this directory under `.agents/skills/svelte-lint` so Copilot agents running in this repository can load it automatically.
