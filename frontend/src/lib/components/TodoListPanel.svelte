<script lang="ts">
	import type { TodoItem, TodoList } from '$lib/api';

	export let list: TodoList;
	export let items: TodoItem[] = [];
	export let draft = '';
	export let onDraftChange: ((value: string) => void) | undefined = undefined;
	export let onAddItem: (() => void) | undefined = undefined;
	export let onToggleItem: ((item: TodoItem) => void) | undefined = undefined;
	export let onRemoveItem: ((item: TodoItem) => void) | undefined = undefined;
	export let onHide: (() => void) | undefined = undefined;

	$: activeItems = items.filter((item) => !item.done);
	$: doneItems = items.filter((item) => item.done);
</script>

<section class="todo-panel">
	<header class="panel-header">
		<div class="panel-title">{list.name}</div>
		<button type="button" class="outline panel-close" on:click={() => onHide?.()} aria-label="Hide panel">✕</button>
	</header>

	<div class="todo-body">
		<div class="item-list-wrap" class:is-empty={items.length === 0}>
			<ul class="item-list">
				{#each activeItems as item (item.id)}
					<li class="item-row">
						<input type="checkbox" checked={!!item.done} on:change={() => onToggleItem?.(item)} />
						<span class="item-text">{item.text}</span>
						<button class="delete-btn" on:click={() => onRemoveItem?.(item)} aria-label="Delete item">✕</button>
					</li>
				{/each}
				{#if doneItems.length}
					<li class="done-divider">Completed</li>
					{#each doneItems as item (item.id)}
						<li class="item-row done">
							<input type="checkbox" checked={!!item.done} on:change={() => onToggleItem?.(item)} />
							<span class="item-text">{item.text}</span>
							<button class="delete-btn" on:click={() => onRemoveItem?.(item)} aria-label="Delete item">✕</button>
						</li>
					{/each}
				{:else if activeItems.length === 0}
					<li class="empty">No items yet.</li>
				{/if}
			</ul>
		</div>

		<form class="new-item-form" on:submit|preventDefault={() => onAddItem?.()}>
			<input
				class="new-item-input"
				value={draft}
				on:input={(event) => onDraftChange?.((event.currentTarget as HTMLInputElement).value)}
				placeholder={`Add item to ${list.name}…`}
				aria-label="New item"
			/>
		</form>
	</div>
</section>

<style>
	.todo-panel {
		border: 1px solid var(--pico-muted-border-color);
		border-radius: 0.75rem;
		padding: 0.65rem 0.8rem;
		min-height: clamp(20rem, 56vh, 38rem);
		display: flex;
		flex-direction: column;
		background: color-mix(in srgb, var(--pico-muted-border-color) 6%, transparent);
		min-width: 0;
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
		font-size: 0.92rem;
		font-weight: 650;
		opacity: 0.9;
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

	.todo-body {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
	}

	.item-list-wrap {
		position: relative;
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}

	.item-list-wrap::after {
		content: '';
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		height: 1.25rem;
		pointer-events: none;
		background: linear-gradient(to bottom, transparent, var(--pico-background-color));
		opacity: 0.95;
	}

	.item-list-wrap.is-empty::after {
		display: none;
	}

	.item-list {
		height: 100%;
		overflow-y: auto;
		list-style: none;
		padding: 0 0.1rem 0 0;
		margin: 0;
	}

	.item-row {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: start;
		gap: 0.6rem;
		padding: 0.45rem 0;
		border-bottom: 1px solid var(--pico-muted-border-color);
	}

	.item-row.done .item-text {
		text-decoration: line-through;
		opacity: 0.5;
	}

	.item-text {
		font-size: 0.95rem;
		line-height: 1.35;
		white-space: normal;
		overflow-wrap: anywhere;
	}

	.done-divider {
		font-size: 0.7rem;
		color: var(--pico-muted-color);
		padding: 0.55rem 0 0.2rem;
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

	.delete-btn:hover {
		opacity: 1;
		color: var(--pico-del-color);
	}

	.new-item-form {
		padding-top: 0.5rem;
		flex-shrink: 0;
	}

	.new-item-input {
		width: 100%;
		background: transparent;
		border: none;
		border-bottom: 1px solid var(--pico-muted-border-color);
		border-radius: 0;
		padding: 0.4rem 0.2rem;
		font-size: 0.88rem;
		outline: none;
		color: inherit;
	}

	.new-item-input:focus {
		border-bottom-color: var(--pico-primary);
	}

	.empty {
		color: var(--pico-muted-color);
		font-size: 0.9rem;
		padding: 1rem 0;
		list-style: none;
	}
</style>