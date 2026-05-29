<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { currentView, type View } from '$lib/stores';

	type SwitcherIcon =
		| { kind: 'text'; value: string }
		| { kind: 'mask'; src: string };

	const views: { id: View; label: string; icon: SwitcherIcon }[] = [
		{ id: 'day', label: 'Day', icon: { kind: 'text', value: '▦' } },
		{ id: 'week', label: 'Week', icon: { kind: 'text', value: '▦▦' } },
		{ id: 'month', label: 'Month', icon: { kind: 'text', value: '▦▦▦' } },
		{
			id: 'weather',
			label: 'Weather',
			icon: {
				kind: 'mask',
				src: '/icons/view-switcher-weather.svg'
			}
		},
		{ id: 'todo', label: 'Todo', icon: { kind: 'text', value: '✓' } },
		{
			id: 'recipes',
			label: 'Recipes',
			icon: {
				kind: 'mask',
				src: '/icons/view-switcher-recipes.svg'
			}
		}
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
		r: 'recipes',
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
		if (event.key === 'Escape' || event.key === 'ArrowDown') {
			event.preventDefault();
			closeSwitcher();
			return;
		}
		const shortcut = shortcutMap[event.key.toLowerCase()];
		if (!shortcut) return;
		event.preventDefault();
		select(shortcut);
	}

	onMount(() => {
		const handleOpen = () => openSwitcher();
		const handleToggle = () => toggleSwitcher();
		window.addEventListener('view-switcher:open', handleOpen);
		window.addEventListener('view-switcher:toggle', handleToggle);
		window.addEventListener('keydown', onWindowKeydown);
		return () => {
			window.removeEventListener('view-switcher:open', handleOpen);
			window.removeEventListener('view-switcher:toggle', handleToggle);
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
					<span class="icon" aria-hidden="true">
						{#if v.icon.kind === 'mask'}
							<span class="icon-mask" style={`--icon-url: url('${v.icon.src}')`}></span>
						{:else}
							{v.icon.value}
						{/if}
					</span>
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
		background: black	;
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
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.15rem;
		height: 1.15rem;
		font-size: 1rem;
	}

	.icon-mask {
		display: block;
		width: 100%;
		height: 100%;
		background: currentColor;
		mask-image: var(--icon-url);
		mask-position: center;
		mask-repeat: no-repeat;
		mask-size: contain;
		-webkit-mask-image: var(--icon-url);
		-webkit-mask-position: center;
		-webkit-mask-repeat: no-repeat;
		-webkit-mask-size: contain;
	}
</style>
