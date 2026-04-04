<script lang="ts">
	import {
		fetchLists, createList, deleteList,
		fetchItems, createItem, patchItem, deleteItem,
		fetchCounter, incCounter
	} from '$lib/api';
	import type { TodoList, TodoItem, CounterState } from '$lib/api';
	import { onMount } from 'svelte';

	let lists: TodoList[] = [];
	let items: Record<number, TodoItem[]> = {};
	let newListName = '';
	let newListType: 'todo' | 'counter' = 'todo';
	let newResetKind: 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly' = 'none';
	let newWeekEndsOn = 0; // Sunday
	let newCounterMode: 'normal' | 'negative' = 'normal';
	let newCounterInitial = 0;

	$: if (newListType === 'counter' && newCounterMode === 'negative' && newCounterInitial === 0) {
		// A negative counter is most useful as a countdown; default to 10 so it visibly works.
		newCounterInitial = 10;
	}
	let newItemText: Record<number, string> = {};
	let openListId: number | null = null;
	let activeListIds: number[] = [];
	let counterState: Record<number, CounterState> = {};
	let showCreate = false;
	const STORAGE_KEY = 'rpi.todoView.selection.v1';

	function resetTitle(kind?: TodoList['reset_kind']): string {
		switch (kind) {
			case 'daily': return 'Resets daily';
			case 'weekly': return 'Resets weekly';
			case 'monthly': return 'Resets monthly';
			case 'yearly': return 'Resets yearly';
			default: return '';
		}
	}

	function typeTitle(list: TodoList): string {
		if ((list.list_type ?? 'todo') !== 'counter') return '';
		const mode = list.counter_mode === 'negative' ? 'Negative counter' : 'Counter';
		const reset = list.reset_kind && list.reset_kind !== 'none' ? ` • ${resetTitle(list.reset_kind)}` : '';
		return `${mode}${reset}`;
	}

	onMount(loadLists);

	function saveSelection() {
		try {
			localStorage.setItem(
				STORAGE_KEY,
				JSON.stringify({ openListId, activeListIds })
			);
		} catch {
			// Ignore storage failures (private mode, etc.)
		}
	}

	function loadSelectionFromStorage() {
		try {
			const raw = localStorage.getItem(STORAGE_KEY);
			if (!raw) return;
			const parsed = JSON.parse(raw);
			if (typeof parsed?.openListId === 'number') openListId = parsed.openListId;
			if (Array.isArray(parsed?.activeListIds)) {
				activeListIds = parsed.activeListIds.filter((x: unknown) => typeof x === 'number');
			}
		} catch {
			// Ignore parse/storage errors
		}
	}

	async function loadLists() {
		// Restore selection early (before applying defaults)
		loadSelectionFromStorage();

		lists = await fetchLists();
		// Preload counter state so newly created counters don't show "Loading…" forever.
		await Promise.all(
			lists
				.filter((l) => (l.list_type ?? 'todo') === 'counter')
				.map((l) => loadCounter(l.id))
		);
		if (lists.length && openListId === null) openListId = lists[0].id;
		if (openListId !== null) {
			// Filter stored selections to existing lists
			const ids = new Set(lists.map((l) => l.id));
			activeListIds = (activeListIds.length ? activeListIds : [openListId]).filter((id) => ids.has(id));
			if (activeListIds.length === 0) activeListIds = [openListId];
			if (!ids.has(openListId)) openListId = activeListIds[0] ?? lists[0].id;

			await Promise.all(activeListIds.map((id) => ensureLoaded(id)));
		}
		saveSelection();
	}

	async function ensureLoaded(id: number) {
		const list = lists.find((l) => l.id === id);
		if (list?.list_type === 'counter') {
			if (!counterState[id]) await loadCounter(id);
			if (!items[id]) items[id] = [];
		} else {
			if (!items[id]) await loadItems(id);
		}
	}

	async function loadItems(listId: number) {
		items[listId] = await fetchItems(listId);
	}

	async function loadCounter(listId: number) {
		counterState[listId] = await fetchCounter(listId);
	}

	async function addList() {
		const name = newListName.trim();
		if (!name) return;
		const list = await createList({
			name,
			list_type: newListType,
			reset_kind: newResetKind,
			week_ends_on: newResetKind === 'weekly' ? newWeekEndsOn : 0,
			counter_mode: newListType === 'counter' ? newCounterMode : 'normal',
			counter_initial: newListType === 'counter' ? newCounterInitial : 0
		});
		lists = [...lists, list];
		items[list.id] = [];
		newListName = '';
		openListId = list.id;
		activeListIds = Array.from(new Set([...activeListIds, list.id]));
		if (list.list_type === 'counter') await loadCounter(list.id);
		saveSelection();
	}

	async function removeList(id: number) {
		await deleteList(id);
		lists = lists.filter((l) => l.id !== id);
		const { [id]: _, ...rest } = items;
		items = rest;
		activeListIds = activeListIds.filter((x) => x !== id);
		if (openListId === id) openListId = activeListIds[0] ?? lists[0]?.id ?? null;
		if (openListId !== null && activeListIds.length === 0) activeListIds = [openListId];
		saveSelection();
	}

	async function addItem(listId: number) {
		const text = (newItemText[listId] ?? '').trim();
		if (!text) return;
		const item = await createItem(listId, text);
		items[listId] = [...(items[listId] ?? []), item];
		newItemText[listId] = '';
	}

	async function toggleItem(item: TodoItem) {
		const done = !item.done;
		await patchItem(item.id, { done });
		items[item.list_id] = items[item.list_id].map((i) =>
			i.id === item.id ? { ...i, done: done ? 1 : 0 } : i
		);
	}

	async function removeItem(item: TodoItem) {
		await deleteItem(item.id);
		items[item.list_id] = items[item.list_id].filter((i) => i.id !== item.id);
	}

	async function selectList(id: number) {
		openListId = id;
		const exists = activeListIds.includes(id);
		activeListIds = exists
			? activeListIds.filter((x) => x !== id)
			: [...activeListIds, id];
		// Always keep at least one panel open.
		if (activeListIds.length === 0) activeListIds = [id];
		await ensureLoaded(id);
		saveSelection();
	}

	async function counterDelta(listId: number, delta: number) {
		const res = await incCounter(listId, delta);
		counterState[listId] = { ...(counterState[listId] ?? await fetchCounter(listId)), value: res.value, today: res.today };
	}

	function itemPlaceholderFor(list?: TodoList | undefined | null): string {
		return `Add item to ${list?.name ?? 'list'}…`;
	}
</script>

<div class="todo-view">
	<aside class="list-sidebar">
		<div class="sidebar-header">
			<div class="sidebar-title">Lists</div>
			<button
				type="button"
				class="outline toggle-create"
				on:click={() => (showCreate = !showCreate)}
				aria-expanded={showCreate}
			>
				{showCreate ? 'Done' : 'Edit'}
			</button>
		</div>
		{#each lists as list}
			<button
				type="button"
				class="list-tab"
				class:active={openListId === list.id}
				class:selected={activeListIds.includes(list.id)}
				on:click={() => selectList(list.id)}
			>
				<span class="list-name">{list.name}</span>
				{#if list.reset_kind && list.reset_kind !== 'none' && (list.list_type ?? 'todo') !== 'counter'}
					<span class="badge" title={resetTitle(list.reset_kind)}>
						{#if list.reset_kind === 'daily'}
							<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 2h12v2H6V2zm0 18h12v2H6v-2zM7 6h10a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2zm0 2v8h10V8H7z"/></svg>
						{:else if list.reset_kind === 'weekly'}
							<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 2v2H5a2 2 0 0 0-2 2v2h18V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2H7zm14 8H3v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V10zm-2 3v2H5v-2h14z"/></svg>
						{:else if list.reset_kind === 'monthly'}
							<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 2v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2V2h-2v2H9V2H7zm12 6H5v12h14V8z"/></svg>
						{:else if list.reset_kind === 'yearly'}
							<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2l2.4 6.2L21 9l-5 4.2L17.2 20 12 16.8 6.8 20 8 13.2 3 9l6.6-.8L12 2z"/></svg>
						{/if}
					</span>
				{/if}
				{#if (list.list_type ?? 'todo') === 'counter'}
					<span class="badge" title={typeTitle(list)}>
						{#if list.counter_mode === 'negative'}
							<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M19 13H5v-2h14v2z"/></svg>
						{:else}
							<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M11 5h2v14h-2V5zm-6 6h14v2H5v-2z"/></svg>
						{/if}
					</span>
				{/if}
				{#if showCreate}
					<span
						class="delete-btn delete-btn--list"
						role="button"
						tabindex="0"
						aria-label="Delete list"
						on:click|stopPropagation={() => removeList(list.id)}
						on:keydown|stopPropagation={(e) => (e.key === 'Enter' || e.key === ' ') && removeList(list.id)}
					>✕</span>
				{/if}
			</button>
		{/each}
		{#if showCreate}
			<form class="new-list-form" on:submit|preventDefault={addList}>
				<div class="field">
					<div class="field-label">Type</div>
					<select bind:value={newListType} aria-label="List type">
						<option value="todo">Todo list</option>
						<option value="counter">Counter</option>
					</select>
				</div>

				<div class="field">
					<div class="field-label">Reset</div>
					<select bind:value={newResetKind} aria-label="Reset schedule">
						<option value="none">No reset</option>
						<option value="daily">Daily</option>
						<option value="weekly">Weekly</option>
						<option value="monthly">Monthly</option>
						<option value="yearly">Yearly</option>
					</select>
				</div>

				{#if newResetKind === 'weekly'}
					<div class="field">
						<div class="field-label">Week ends</div>
						<select bind:value={newWeekEndsOn} aria-label="Week ends on">
							<option value={0}>Sunday</option>
							<option value={1}>Monday</option>
							<option value={2}>Tuesday</option>
							<option value={3}>Wednesday</option>
							<option value={4}>Thursday</option>
							<option value={5}>Friday</option>
							<option value={6}>Saturday</option>
						</select>
					</div>
				{/if}

				{#if newListType === 'counter'}
					<div class="field">
						<div class="field-label">Mode</div>
						<select bind:value={newCounterMode} aria-label="Counter mode">
							<option value="normal">Normal</option>
							<option value="negative">Negative (countdown)</option>
						</select>
					</div>
					<div class="field">
						<div class="field-label">Initial</div>
						<input
							type="number"
							bind:value={newCounterInitial}
							class="small-input"
							aria-label="Initial value"
							placeholder="10"
						/>
					</div>
				{/if}

				<div class="field">
					<div class="field-label">Name</div>
					<input
						class="new-list-input"
						bind:value={newListName}
						placeholder="e.g. Groceries"
						aria-label="New list name"
					/>
				</div>
				<button type="submit" class="outline create-btn">Create</button>
			</form>
		{/if}
	</aside>

	<main class="list-content">
		{#if activeListIds.length}
			<div class="panel-grid">
				{#each activeListIds as panelId (panelId)}
					{@const panelList = lists.find((l) => l.id === panelId)}
					{#if panelList}
						<section class="panel" class:panelActive={panelId === openListId}>
							<header class="panel-header">
								<div class="panel-title">{panelList.name}</div>
								<button type="button" class="outline panel-close" on:click={() => selectList(panelId)} aria-label="Hide panel">✕</button>
							</header>

							{#if panelList.list_type === 'counter'}
								{@const st = counterState[panelId]}
								{#if st}
									<div class="counter-card">
										<div class="counter-value">{st.value}</div>
										<div class="counter-sub">today: +{st.today}</div>
										<div class="counter-buttons">
											<button class="outline" on:click={() => counterDelta(panelId, 1)}>+1</button>
											<button class="outline" on:click={() => counterDelta(panelId, -1)}>-1</button>
											<button class="outline" on:click={() => counterDelta(panelId, 10)}>+10</button>
											<button class="outline" on:click={() => counterDelta(panelId, -10)}>-10</button>
										</div>
									</div>
								{:else}
									<p class="empty">Loading counter…</p>
								{/if}
							{:else}
								{@const panelItems = items[panelId] ?? []}
								{@const activeItems = panelItems.filter((i) => !i.done)}
								{@const doneItems = panelItems.filter((i) => i.done)}

								<ul class="item-list">
									{#each activeItems as item (item.id)}
										<li class="item-row">
											<input type="checkbox" checked={!!item.done} on:change={() => toggleItem(item)} />
											<span class="item-text">{item.text}</span>
											<button class="delete-btn" on:click={() => removeItem(item)} aria-label="Delete item">✕</button>
										</li>
									{/each}
									{#if doneItems.length}
										<li class="done-divider">Completed</li>
										{#each doneItems as item (item.id)}
											<li class="item-row done">
												<input type="checkbox" checked={!!item.done} on:change={() => toggleItem(item)} />
												<span class="item-text">{item.text}</span>
												<button class="delete-btn" on:click={() => removeItem(item)} aria-label="Delete item">✕</button>
											</li>
										{/each}
									{/if}
								</ul>

								<form class="new-item-form" on:submit|preventDefault={() => addItem(panelId)}>
									<input
										class="new-item-input"
										bind:value={newItemText[panelId]}
										placeholder={itemPlaceholderFor(panelList)}
										aria-label="New item"
									/>
								</form>
							{/if}
						</section>
					{/if}
				{/each}
			</div>
		{:else if lists.length === 0}
			<p class="empty">No lists yet. Create one on the left.</p>
		{/if}
	</main>
</div>

<style>
	.todo-view {
		display: flex;
		height: 100vh;
		overflow: hidden;
	}

	.list-sidebar {
		width: 14rem;
		flex-shrink: 0;
		border-right: 1px solid var(--pico-muted-border-color);
		display: flex;
		flex-direction: column;
		overflow-y: auto;
	}

	.sidebar-header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.5rem 0.6rem;
		border-bottom: 1px solid var(--pico-muted-border-color);
		position: sticky;
		top: 0;
		background: var(--pico-background-color);
		z-index: 1;
	}

	.sidebar-title {
		font-size: 0.85rem;
		opacity: 0.7;
		font-weight: 600;
		line-height: 1.1;
	}

	.toggle-create {
		font-size: 0.75rem;
		padding: 0.2rem 0.45rem;
		line-height: 1.1;
		align-self: baseline;
	}

	.list-tab {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.6rem 0.8rem;
		cursor: pointer;
		border-bottom: 1px solid var(--pico-muted-border-color);
		user-select: none;
		background: transparent;
		border-left: none;
		border-right: none;
	}

	.list-tab.active {
		background: var(--pico-primary-background);
	}

	.list-tab.selected {
		background: color-mix(in srgb, var(--pico-primary) 12%, transparent);
	}

	.list-tab.selected.active {
		background: color-mix(in srgb, var(--pico-primary) 20%, transparent);
	}

	.list-name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.9rem;
	}

	.new-list-form {
		padding: 0.5rem;
		margin-top: auto;
		font-size: 0.8rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		margin-bottom: 0.45rem;
	}

	.field-label {
		font-size: 0.62rem;
		letter-spacing: 0.02em;
		opacity: 0.65;
		text-transform: uppercase;
	}

	.field select,
	.field input {
		font-size: 0.8rem;
		padding: 0.2rem 0.35rem;
	}

	.create-btn {
		width: 100%;
		margin-top: 0.25rem;
	}

	.small-input {
		font-size: 0.8rem;
		padding: 0.2rem 0.35rem;
	}

	.small-input {
		width: 6rem;
	}

	.new-list-input,
	.new-item-input {
		width: 100%;
		background: transparent;
		border: none;
		border-bottom: 1px solid var(--pico-muted-border-color);
		border-radius: 0;
		padding: 0.3rem 0.2rem;
		font-size: 0.8rem;
		outline: none;
		color: inherit;
	}

	:global(.badge) {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.25rem;
		height: 1.25rem;
		border: 1px solid var(--pico-muted-border-color);
		border-radius: 0.45rem;
		opacity: 0.9;
		margin-left: 0.35rem;
		flex-shrink: 0;
		background: color-mix(in srgb, var(--pico-muted-border-color) 10%, transparent);
	}

	:global(.badge svg) {
		width: 0.9rem;
		height: 0.9rem;
		display: block;
	}

	.new-list-input:focus,
	.new-item-input:focus {
		border-bottom-color: var(--pico-primary);
	}

	.list-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		padding: 0.5rem 1rem;
	}

	.panel-grid {
		flex: 1;
		overflow: auto;
		display: grid;
		gap: 0.75rem;
		grid-template-columns: repeat(auto-fit, minmax(22rem, 1fr));
		align-content: start;
		padding-bottom: 0.5rem;
	}

	.panel {
		border: 1px solid var(--pico-muted-border-color);
		border-radius: 0.6rem;
		padding: 0.6rem 0.75rem;
		min-height: 14rem;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		background: color-mix(in srgb, var(--pico-muted-border-color) 6%, transparent);
	}

	.panel.panelActive {
		background: color-mix(in srgb, var(--pico-muted-border-color) 6%, transparent);
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		padding-bottom: 0.4rem;
		margin-bottom: 0.4rem;
		border-bottom: 1px solid var(--pico-muted-border-color);
		flex-shrink: 0;
	}

	.panel-title {
		font-size: 0.9rem;
		font-weight: 650;
		opacity: 0.85;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.panel-close {
		padding: 0.15rem 0.4rem;
		font-size: 0.85rem;
		line-height: 1;
		opacity: 0.8;
	}

	.item-list {
		flex: 1;
		overflow-y: auto;
		list-style: none;
		padding: 0;
		margin: 0;
	}

	/* Optional: inside each panel, use columns when the panel is wide enough */
	@media (min-width: 55rem) {
		.panel .item-list {
			column-width: 20rem;
			column-gap: 1.15rem;
		}
		.panel .item-row,
		.panel .done-divider {
			break-inside: avoid;
		}
	}

	.item-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0;
		border-bottom: 1px solid var(--pico-muted-border-color);
	}

	.item-row.done .item-text {
		text-decoration: line-through;
		opacity: 0.5;
	}

	.item-text {
		flex: 1;
		font-size: 0.95rem;
	}

	.done-divider {
		font-size: 0.7rem;
		color: var(--pico-muted-color);
		padding: 0.5rem 0 0.2rem;
		list-style: none;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.delete-btn {
		background: none;
		border: none;
		color: var(--pico-muted-color);
		cursor: pointer;
		font-size: 0.75rem;
		padding: 0.1rem 0.3rem;
		line-height: 1;
		opacity: 0.4;
		flex-shrink: 0;
	}

	.delete-btn--list {
		font-size: 1.25rem;
		padding: 0.15rem 0.35rem;
		opacity: 0.6;
	}

	.counter-card {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		padding: 1rem 0.5rem;
	}

	.counter-value {
		font-size: 2.2rem;
		font-variant-numeric: tabular-nums;
		font-weight: 700;
	}

	.counter-sub {
		font-size: 0.8rem;
		opacity: 0.7;
	}

	.counter-buttons {
		display: flex;
		gap: 0.35rem;
		flex-wrap: wrap;
	}

	.delete-btn:hover {
		opacity: 1;
		color: var(--pico-del-color);
	}

	.new-item-form {
		padding: 0.5rem 0;
		flex-shrink: 0;
	}

	.empty {
		color: var(--pico-muted-color);
		font-size: 0.9rem;
		padding: 1rem 0;
	}
</style>
