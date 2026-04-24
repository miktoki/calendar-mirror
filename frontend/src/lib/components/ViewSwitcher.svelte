<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { currentView, type View } from '$lib/stores';

	const views: { id: View; label: string; icon: string }[] = [
		{ id: 'day',     label: 'Day',     icon: '▦' },
		{ id: 'week',    label: 'Week',    icon: '▦▦' },
		{ id: 'month',   label: 'Month',   icon: '▦▦▦' },
		{ id: 'weather', label: 'Weather', icon: '☁' },
		{ id: 'todo',    label: 'Todo',    icon: '✓' },
	];

	let open = false;
	let navEl: HTMLElement | null = null;
	let toggleEl: HTMLButtonElement | null = null;
	const shortcutMap: Record<string, View> = {
		'1': 'day',
		'2': 'week',
		'3': 'month',
		'4': 'weather',
		'5': 'todo',
		d: 'day',
		w: 'week',
		m: 'month',
		h: 'weather',
		t: 'todo',
	};

	function closeSwitcher() {
		open = false;
	}

	function select(v: View) {
		closeSwitcher();
		currentView.set(v);
	}

	function openSwitcher() {
		open = true;
	}

	function toggleSwitcher() {
		open = !open;
	}

	function onWindowKeydown(event: KeyboardEvent) {
		if (!open || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
		const target = event.target;
		if (target instanceof HTMLElement && target.closest('input, textarea, select, [contenteditable="true"]')) return;
		const shortcut = shortcutMap[event.key.toLowerCase()];
		if (!shortcut) return;
		event.preventDefault();
		select(shortcut);
	}

	onMount(() => {
		const handleOpen = () => openSwitcher();
		window.addEventListener('view-switcher:open', handleOpen);
		window.addEventListener('keydown', onWindowKeydown);
		return () => {
			window.removeEventListener('view-switcher:open', handleOpen);
			window.removeEventListener('keydown', onWindowKeydown);
		};
	});

	onDestroy(() => {
		navEl = null;
	});
</script>

<div class="switcher" class:open>
	{#if open}
		<nav bind:this={navEl}>
			{#each views as v}
				<button
					class="outline"
					class:active={$currentView === v.id}
					on:click={() => select(v.id)}
					aria-label={v.label}
				>
					<span class="icon">{v.icon}</span>
					<span class="label">{v.label}</span>
				</button>
			{/each}
		</nav>
	{/if}

	<button
		bind:this={toggleEl}
		class="toggle outline"
		on:click={toggleSwitcher}
		aria-label="Switch view"
	>
		☰
	</button>
</div>

<style>
	.switcher {
		position: fixed;
		bottom: 1.5rem;
		right: 1.5rem;
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.5rem;
		z-index: 100;
	}

	nav {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.4rem;
	}

	nav button {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.45rem 0.9rem;
		font-size: 0.85rem;
		border-radius: 2rem;
		white-space: nowrap;
		backdrop-filter: blur(6px);
	}

	nav button.active {
		background: var(--pico-primary-background);
		color: var(--pico-primary-inverse);
		border-color: var(--pico-primary-border);
	}

	.toggle {
		width: 3rem;
		height: 3rem;
		border-radius: 50%;
		font-size: 1.2rem;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		backdrop-filter: blur(6px);
	}

	.icon {
		font-size: 1rem;
	}
</style>
