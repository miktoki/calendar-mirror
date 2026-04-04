<script lang="ts">
	import '@picocss/pico/css/pico.min.css';
	import ViewSwitcher from '$lib/components/ViewSwitcher.svelte';
	import { currentView } from '$lib/stores';
</script>

<main>
	<slot />
</main>

<ViewSwitcher />

<style>
	:global(*) {
		box-sizing: border-box;
	}

	:global(html, body) {
		margin: 0;
		padding: 0;
		height: 100%;
		overflow: hidden;
		background: var(--pico-background-color);
	}

	main {
		width: 100vw;
		height: 100vh;
		overflow: hidden;
	}
</style>
