<script lang="ts">
	export let title: string;
	export let items: Array<{ id: number; label: string }>;
	export let activeId: number | null = null;
	export let secondaryIds: number[] = [];
	export let showCreate: boolean = false;
	export let onSelect: (id: number) => void;
	export let onDelete: ((id: number) => void) | undefined = undefined;
	export let onNew: (() => void) | undefined = undefined;
</script>

<aside class="sidebar">
	<div class="sidebar-header">
		<div class="sidebar-title">{title}</div>
		<slot name="header-actions" />
		<button
			type="button"
			class="outline toggle-create"
			on:click={() => (showCreate = !showCreate)}
			aria-expanded={showCreate}
		>
			{showCreate ? 'Done' : 'Edit'}
		</button>
	</div>

	{#if showCreate && onNew}
		<button type="button" class="new-item-row" on:click={onNew} aria-label="Create new">
			<span class="new-item-plus">+</span>
			<span class="new-item-label">New…</span>
		</button>
	{/if}

	{#each items as item (item.id)}
		<button
			type="button"
			class="sidebar-item"
			class:active={activeId === item.id}
			class:selected={secondaryIds.includes(item.id)}
			on:click={() => onSelect(item.id)}
		>
			<span class="item-label">{item.label}</span>
			<slot name="item-meta" {item} />
			{#if showCreate && onDelete}
				<span
					class="delete-btn"
					role="button"
					tabindex="0"
					aria-label="Delete"
					on:click|stopPropagation={() => onDelete?.(item.id)}
					on:keydown|stopPropagation={(e) =>
						(e.key === 'Enter' || e.key === ' ') && onDelete?.(item.id)}
				>✕</span>
			{/if}
		</button>
	{/each}

	{#if showCreate}
		<slot name="create-form" />
	{/if}
</aside>

<style>
	.sidebar {
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

	:global(.sidebar-action-btn) {
		font-size: 0.8rem;
		padding: 0.2rem 0.45rem;
		line-height: 1.1;
		align-self: baseline;
	}

	.sidebar-item {
		display: flex;
		align-items: center;
		padding: 0.6rem 0.8rem;
		cursor: pointer;
		border-bottom: 1px solid var(--pico-muted-border-color);
		user-select: none;
		background: transparent;
		border-left: none;
		border-right: none;
		gap: 0.55rem;
		position: relative;
		padding-right: 2.2rem;
	}

	.sidebar-item.active {
		background: var(--pico-primary-background);
	}

	.sidebar-item.selected {
		background: color-mix(in srgb, var(--pico-primary) 12%, transparent);
	}

	.sidebar-item.selected.active {
		background: color-mix(in srgb, var(--pico-primary) 20%, transparent);
	}

	.item-label {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.9rem;
	}

	.delete-btn {
		font-size: 1.25rem;
		padding: 0.15rem 0.35rem;
		opacity: 0.6;
		position: absolute;
		right: 0.3rem;
		top: 50%;
		transform: translateY(-50%);
	}

	.delete-btn:hover {
		opacity: 1;
		color: var(--pico-del-color);
		cursor: pointer;
	}

	.new-item-row {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.5rem 0.8rem;
		border-bottom: 1px solid var(--pico-muted-border-color);
		background: color-mix(in srgb, var(--pico-primary) 6%, transparent);
		border-left: none;
		border-right: none;
		cursor: pointer;
		width: 100%;
		text-align: left;
		color: var(--pico-primary);
	}

	.new-item-plus {
		font-size: 1rem;
		font-weight: 700;
		line-height: 1;
	}

	.new-item-label {
		font-size: 0.85rem;
	}
</style>
