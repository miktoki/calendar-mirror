<script lang="ts">
	import { currentView, type View } from '$lib/stores';

	const views: { id: View; label: string; icon: string }[] = [
		{ id: 'day',     label: 'Day',     icon: '▦' },
		{ id: 'week',    label: 'Week',    icon: '▦▦' },
		{ id: 'month',   label: 'Month',   icon: '▦▦▦' },
		{ id: 'weather', label: 'Weather', icon: '☁' },
		{ id: 'todo',    label: 'Todo',    icon: '✓' },
	];

	let open = false;

	function select(v: View) {
		currentView.set(v);
		open = false;
	}
</script>

<div class="switcher" class:open>
	{#if open}
		<nav>
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
		class="toggle outline"
		on:click={() => (open = !open)}
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
