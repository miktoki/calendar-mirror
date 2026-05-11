<script lang="ts">
	import {
		fetchLists, createList, deleteList,
		fetchItems, createItem, patchItem, deleteItem,
		fetchCounter, incCounter
	} from '$lib/api';
	import type { TodoList, TodoItem, CounterState } from '$lib/api';
	import { onMount } from 'svelte';
	import CounterPanel from './CounterPanel.svelte';
	import TodoListPanel from './TodoListPanel.svelte';
	import Sidebar from './Sidebar.svelte';

	type CounterButton = {
		label: string;
		delta: number;
		disabled: boolean;
	};

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
	let counterError: Record<number, string> = {};
	let showCreate = false;
	const STORAGE_KEY = 'rpi.todoView.selection.v1';

	function messageFromError(error: unknown, fallback: string): string {
		return error instanceof Error ? error.message : fallback;
	}

	function formatCounterToday(value: number): string {
		if (value === 0) return '0';
		return `${value > 0 ? '+' : ''}${value}`;
	}

	function canApplyCounterDelta(state: CounterState, delta: number): boolean {
		const nextValue = state.value + delta;
		if (state.mode === 'negative') {
			return nextValue >= 0 && nextValue <= state.initial;
		}
		return nextValue >= 0;
	}

	function counterButtons(state: CounterState): CounterButton[] {
		const negativeOrder = [
			{ label: '-1', delta: -1 },
			{ label: '-10', delta: -10 },
			{ label: '+1', delta: 1 },
			{ label: '+10', delta: 10 },
		];
		const normalOrder = [
			{ label: '+1', delta: 1 },
			{ label: '+10', delta: 10 },
			{ label: '-1', delta: -1 },
			{ label: '-10', delta: -10 },
		];
		const ordered = state.mode === 'negative' ? negativeOrder : normalOrder;
		return ordered.map((button) => ({ ...button, disabled: !canApplyCounterDelta(state, button.delta) }));
	}

	function resetTitle(kind?: TodoList['reset_kind']): string {
		switch (kind) {
			case 'daily': return 'Resets daily';
			case 'weekly': return 'Resets weekly';
			case 'monthly': return 'Resets monthly';
			case 'yearly': return 'Resets yearly';
			default: return '';
		}
	}

	function resetMarker(kind?: TodoList['reset_kind']): string {
		switch (kind) {
			case 'daily': return 'D';
			case 'weekly': return 'W';
			case 'monthly': return 'M';
			case 'yearly': return 'Y';
			default: return '';
		}
	}

	function typeTitle(list: TodoList): string {
		if ((list.list_type ?? 'todo') !== 'counter') return 'Todo list';
		const mode = list.counter_mode === 'negative' ? 'Countdown' : 'Counter';
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
		await Promise.allSettled(
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
		try {
			counterState[listId] = await fetchCounter(listId);
			delete counterError[listId];
			counterError = { ...counterError };
		} catch (error: unknown) {
			const { [listId]: _removed, ...rest } = counterState;
			counterState = rest;
			counterError[listId] = messageFromError(error, 'Failed to load counter');
			counterError = { ...counterError };
		}
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
		const { [id]: _counterState, ...counterRest } = counterState;
		const { [id]: _counterError, ...errorRest } = counterError;
		items = rest;
		counterState = counterRest;
		counterError = errorRest;
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
		delete counterError[listId];
		counterError = { ...counterError };
		counterState[listId] = { ...(counterState[listId] ?? await fetchCounter(listId)), value: res.value, today: res.today };
	}

	function updateDraft(listId: number, value: string) {
		newItemText = { ...newItemText, [listId]: value };
	}

	function itemPlaceholderFor(list?: TodoList | undefined | null): string {
		return `Add item to ${list?.name ?? 'list'}…`;
	}
</script>

<div class="todo-view">
	<Sidebar
		title="Lists"
		items={lists.map((l) => ({ id: l.id, label: l.name }))}
		activeId={openListId}
		secondaryIds={activeListIds}
		bind:showCreate
		onSelect={selectList}
		onDelete={removeList}
	>
		<svelte:fragment slot="item-meta" let:item>
			{@const list = lists.find((l) => l.id === item.id)}
			{#if list}
				<span class="list-meta">
					<span class="badge" title={typeTitle(list)}>
						{#if (list.list_type ?? 'todo') === 'counter'}
							{#if list.counter_mode === 'negative'}
								<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M9 4h6M9 20h6M8 6h8M8 18h8M9 6c0 3 3 3.8 3 6s-3 3-3 6M15 6c0 3-3 3.8-3 6s3 3 3 6"/></svg>
							{:else}
								<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M6.5 7v10M10.5 7v10M14.5 7v10M18.5 7v10M5.5 16.5 19.5 8.5"/></svg>
							{/if}
						{:else}
							<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M11 7h8M11 12h8M11 17h8M4.5 7.5l1.6 1.6 2.4-3.1M4.5 12.5l1.6 1.6 2.4-3.1M4.5 17.5l1.6 1.6 2.4-3.1"/></svg>
						{/if}
					</span>
					{#if list.reset_kind && list.reset_kind !== 'none'}
						<span class="badge badge--muted" title={resetTitle(list.reset_kind)}>
							{resetMarker(list.reset_kind)}
						</span>
					{/if}
				</span>
			{/if}
		</svelte:fragment>

		<svelte:fragment slot="create-form">
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
		</svelte:fragment>
	</Sidebar>

	<main class="list-content">
		{#if activeListIds.length}
			<div class="panel-grid">
				{#each activeListIds as panelId (panelId)}
					{@const panelList = lists.find((l) => l.id === panelId)}
					{#if panelList}
						{#if panelList.list_type === 'counter'}
							<CounterPanel
								list={panelList}
								state={counterState[panelId] ?? null}
								error={counterError[panelId] ?? ''}
								buttons={counterState[panelId] ? counterButtons(counterState[panelId]) : []}
								todayLabel={counterState[panelId] ? formatCounterToday(counterState[panelId].today) : '0'}
								onDelta={(delta) => counterDelta(panelId, delta)}
								onHide={() => selectList(panelId)}
							/>
						{:else}
							<TodoListPanel
								list={panelList}
								items={items[panelId] ?? []}
								draft={newItemText[panelId] ?? ''}
								onDraftChange={(value) => updateDraft(panelId, value)}
								onAddItem={() => addItem(panelId)}
								onToggleItem={toggleItem}
								onRemoveItem={removeItem}
								onHide={() => selectList(panelId)}
							/>
						{/if}
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

	.list-meta {
		display: inline-flex;
		flex-direction: column;
		align-items: flex-end;
		justify-content: center;
		gap: 0.08rem;
		flex-shrink: 0;
		position: absolute;
		right: 0.8rem;
		top: 50%;
		transform: translateY(-50%);
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
		width: 6rem;
	}

	.new-list-input {
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

	.new-list-input:focus {
		border-bottom-color: var(--pico-primary);
	}

	:global(.badge) {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 0.9rem;
		height: 0.9rem;
		flex-shrink: 0;
		color: color-mix(in srgb, var(--pico-color) 72%, transparent);
		opacity: 0.82;
		font-size: 0.6rem;
		font-weight: 700;
		line-height: 1;
	}

	:global(.badge svg) {
		width: 0.9rem;
		height: 0.9rem;
		display: block;
	}

	:global(.badge--muted) {
		color: var(--pico-muted-color);
		opacity: 0.72;
	}

	.list-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		padding: 0.5rem 0.85rem;
	}

	.panel-grid {
		flex: 1;
		overflow-y: auto;
		overflow-x: hidden;
		display: grid;
		gap: 0.75rem;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr));
		align-content: start;
		padding-bottom: 0.5rem;
		grid-auto-flow: dense;
	}

	:global(.todo-panel) {
		min-width: 0;
	}

	@media (min-width: 68rem) {
		.panel-grid {
			grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
		}

		:global(.todo-panel) {
			grid-column: span 2;
		}
	}

	.empty {
		color: var(--pico-muted-color);
		font-size: 0.9rem;
		padding: 1rem 0;
	}
</style>
