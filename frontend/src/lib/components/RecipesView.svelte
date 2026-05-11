<script lang="ts">
	import { onMount } from 'svelte';
	import { fetchRecipes, fetchRecipe, createRecipe, updateRecipe, deleteRecipe } from '$lib/api';
	import type { RecipeSummary, Recipe } from '$lib/api';
	import Sidebar from './Sidebar.svelte';

	type DraftIngredient = { name: string; amount: string; unit: string };
	type DraftGroup = { description: string; ingredients: DraftIngredient[] };

	const SCALE_OPTIONS: { value: number; label: string }[] = [
		{ value: 0.25, label: '¼×' },
		{ value: 0.5, label: '½×' },
		{ value: 1, label: '1×' },
		{ value: 1.5, label: '1½×' },
		{ value: 2, label: '2×' },
		{ value: 4, label: '4×' },
	];

	let recipes: RecipeSummary[] = [];
	let selectedId: number | null = null;
	let selectedRecipe: Recipe | null = null;
	let loadingRecipe = false;
	let showCreate = false;
	let creating = false;
	let editing = false;
	let scale = 1;

	let draftTitle = '';
	let draftGroups: DraftGroup[] = emptyGroups();
	let draftSteps: string[] = [''];

	function emptyGroups(): DraftGroup[] {
		return [{ description: '', ingredients: [{ name: '', amount: '', unit: '' }] }];
	}

	onMount(async () => {
		recipes = await fetchRecipes();
		if (recipes.length) {
			selectedId = recipes[0].id;
			await loadRecipe(selectedId);
		}
	});

	async function loadRecipe(id: number) {
		loadingRecipe = true;
		try {
			selectedRecipe = await fetchRecipe(id);
		} finally {
			loadingRecipe = false;
		}
	}

	async function selectRecipe(id: number) {
		if (selectedId === id && selectedRecipe) {
			if (showCreate && !editing && !creating) _beginEdit();
			return;
		}
		creating = false;
		editing = false;
		selectedId = id;
		selectedRecipe = null;
		await loadRecipe(id);
		if (showCreate) _beginEdit();
	}

	async function removeRecipe(id: number) {
		await deleteRecipe(id);
		recipes = recipes.filter((r) => r.id !== id);
		if (selectedId === id) {
			creating = false;
			editing = false;
			selectedId = recipes[0]?.id ?? null;
			selectedRecipe = null;
			if (selectedId !== null) await loadRecipe(selectedId);
		}
	}

	function startCreate() {
		editing = false;
		creating = true;
		selectedId = null;
		selectedRecipe = null;
		draftTitle = '';
		draftGroups = emptyGroups();
		draftSteps = [''];
		savedPayload = '';
	}

	function _beginEdit() {
		if (!selectedRecipe) return;
		creating = false;
		editing = true;
		draftTitle = selectedRecipe.title;
		draftGroups = selectedRecipe.groups.length
			? selectedRecipe.groups.map((g) => ({
					description: g.description,
					ingredients: g.ingredients.map((i) => ({
						name: i.name,
						amount: i.amount ? String(i.amount) : '',
						unit: i.unit,
					})),
				}))
			: emptyGroups();
		draftSteps = selectedRecipe.instructions.length
			? selectedRecipe.instructions.map((s) => s.text)
			: [''];
		savedPayload = JSON.stringify(buildPayload());
	}

	function cancelForm() {
		creating = false;
		editing = false;
	}

	function addGroup() {
		draftGroups = [...draftGroups, { description: '', ingredients: [{ name: '', amount: '', unit: '' }] }];
	}

	function removeGroup(gi: number) {
		if (draftGroups.length <= 1) return;
		draftGroups = draftGroups.filter((_, i) => i !== gi);
	}

	function addIngredient(gi: number) {
		draftGroups = draftGroups.map((g, i) =>
			i === gi ? { ...g, ingredients: [...g.ingredients, { name: '', amount: '', unit: '' }] } : g
		);
	}

	function removeIngredient(gi: number, ii: number) {
		draftGroups = draftGroups.map((g, i) =>
			i === gi ? { ...g, ingredients: g.ingredients.filter((_, j) => j !== ii) } : g
		);
	}

	function addStep() {
		draftSteps = [...draftSteps, ''];
	}

	function removeStep(i: number) {
		draftSteps = draftSteps.length > 1 ? draftSteps.filter((_, j) => j !== i) : [''];
	}

	function buildPayload() {
		return {
			title: draftTitle.trim(),
			groups: draftGroups
				.map((g) => ({
					description: g.description.trim(),
					ingredients: g.ingredients
						.filter((i) => i.name.trim())
						.map((i) => ({ name: i.name.trim(), amount: parseFloat(i.amount) || 0, unit: i.unit.trim() })),
				}))
				.filter((g) => g.ingredients.length > 0),
			instructions: draftSteps.map((t) => ({ text: t.trim() })).filter((s) => s.text),
		};
	}

	async function submitCreate() {
		const payload = buildPayload();
		if (!payload.title) return;
		const created = await createRecipe(payload);
		recipes = [...recipes, created].sort((a, b) =>
			a.title.localeCompare(b.title, undefined, { sensitivity: 'base' })
		);
		creating = false;
		showCreate = false;
		selectedId = created.id;
		selectedRecipe = null;
		await loadRecipe(created.id);
	}

	async function submitEdit() {
		if (!selectedRecipe) return;
		const payload = buildPayload();
		if (!payload.title) return;
		const updated = await updateRecipe(selectedRecipe.id, payload);
		recipes = recipes
			.map((r) => (r.id === updated.id ? { ...r, title: updated.title } : r))
			.sort((a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: 'base' }));
		selectedRecipe = updated;
		editing = false;
		showCreate = false;
	}

	function formatAmount(amount: number, s: number): string {
		if (!amount) return '';
		const v = amount * s;
		const FRACS: [number, string][] = [
			[1 / 4, '¼'], [1 / 3, '⅓'], [1 / 2, '½'], [2 / 3, '⅔'], [3 / 4, '¾'],
		];
		const whole = Math.floor(v);
		const frac = v - whole;
		for (const [f, sym] of FRACS) {
			if (Math.abs(frac - f) < 0.04) return whole > 0 ? `${whole}${sym}` : sym;
		}
		if (Math.abs(frac) < 0.04) return String(whole);
		return v < 10 ? v.toFixed(1).replace(/\.0$/, '') : String(Math.round(v));
	}

	let savedPayload: string = '';

	$: hasScalableIngredients = selectedRecipe?.groups.some((g) => g.ingredients.some((i) => i.amount > 0)) ?? false;
	$: multipleGroups = draftGroups.length > 1;
	$: hasChanges = creating || JSON.stringify(buildPayload()) !== savedPayload;
</script>

<div class="recipes-view">
	<Sidebar
		title="Recipes"
		items={recipes.map((r) => ({ id: r.id, label: r.title }))}
		activeId={selectedId}
		bind:showCreate
		onSelect={selectRecipe}
		onDelete={removeRecipe}
		onNew={startCreate}
	/>

	<main class="recipe-content">
		{#if creating || editing}
			<section class="recipe-form">
				<div class="form-actions form-actions--bar">
					<h2 class="form-title">{creating ? 'New Recipe' : `Edit: ${selectedRecipe?.title ?? ''}`}</h2>
					<div class="form-btns">
						<button type="button" class="outline" on:click={cancelForm}>Cancel</button>
						<button type="button" disabled={!hasChanges} on:click={creating ? submitCreate : submitEdit}>Save</button>
					</div>
				</div>

				<div class="form-body">
					<div class="form-section">
						<div class="section-label">Title</div>
						<input class="title-input" bind:value={draftTitle} placeholder="Recipe title" aria-label="Recipe title" />
					</div>

					<div class="form-section">
						<div class="section-label">Ingredients</div>
						{#each draftGroups as group, gi}
							<div class="group-block">
								{#if multipleGroups}
									<div class="group-header-row">
										<input
											class="bare-input group-desc-input"
											bind:value={group.description}
											placeholder="Group name (e.g. Sauce)"
										/>
										<button type="button" class="icon-btn" on:click={() => removeGroup(gi)} aria-label="Remove group">✕</button>
									</div>
								{/if}
								<div class="ing-form-grid ing-form-header">
									<span>Ingredient</span><span>Amount</span><span>Unit</span><span></span>
								</div>
								{#each group.ingredients as _ing, ii}
									<div class="ing-form-grid">
										<input class="bare-input" bind:value={group.ingredients[ii].name} placeholder="e.g. Flour" />
										<input class="bare-input amount-input" bind:value={group.ingredients[ii].amount} placeholder="250" />
										<input class="bare-input unit-input" bind:value={group.ingredients[ii].unit} placeholder="g" />
										<button type="button" class="icon-btn" on:click={() => removeIngredient(gi, ii)} aria-label="Remove">✕</button>
									</div>
								{/each}
								<button type="button" class="add-link" on:click={() => addIngredient(gi)}>+ ingredient</button>
							</div>
						{/each}
						<button type="button" class="add-link" on:click={addGroup}>+ group</button>
					</div>

					<div class="form-section">
						<div class="section-label">Instructions</div>
						{#each draftSteps as _step, si}
							<div class="step-row">
								<span class="step-num">{si + 1}.</span>
								<textarea class="step-textarea" bind:value={draftSteps[si]} rows="2" placeholder="Step…"></textarea>
								<button type="button" class="icon-btn" on:click={() => removeStep(si)} aria-label="Remove step">✕</button>
							</div>
						{/each}
						<button type="button" class="add-link" on:click={addStep}>+ step</button>
					</div>
				</div>

				<div class="form-actions form-actions--bar form-actions--bottom">
					<div class="form-btns">
						<button type="button" class="outline" on:click={cancelForm}>Cancel</button>
						<button type="button" disabled={!hasChanges} on:click={creating ? submitCreate : submitEdit}>Save</button>
					</div>
				</div>
			</section>
		{:else if loadingRecipe}
			<p class="muted">Loading…</p>
		{:else if selectedRecipe}
			<article class="recipe-detail">
				<header class="detail-header">
					<h2 class="recipe-title">{selectedRecipe.title}</h2>
				</header>

				{#if hasScalableIngredients}
					<div class="scale-row">
						<label class="scale-label" for="scale-select">Scale</label>
						<select id="scale-select" class="scale-select" bind:value={scale}>
							{#each SCALE_OPTIONS as opt}
								<option value={opt.value}>{opt.label}</option>
							{/each}
						</select>
					</div>
				{/if}

				{#if selectedRecipe.groups.length > 0}
					<section class="detail-section">
						<div class="section-title">Ingredients</div>
						{#if selectedRecipe.groups.length === 1}
							<div class="ing-grid">
								{#each selectedRecipe.groups[0].ingredients as ing}
									<span class="col-name">{ing.name}</span>
									<span class="col-amount">{formatAmount(ing.amount, scale)}</span>
									<span class="col-unit">{ing.unit}</span>
								{/each}
							</div>
						{:else}
							{#each selectedRecipe.groups as group}
								<div class="ingredient-group">
									{#if group.description}
										<div class="group-label">{group.description}</div>
									{/if}
									<div class="ing-grid">
										{#each group.ingredients as ing}
											<span class="col-name">{ing.name}</span>
											<span class="col-amount">{formatAmount(ing.amount, scale)}</span>
											<span class="col-unit">{ing.unit}</span>
										{/each}
									</div>
								</div>
							{/each}
						{/if}
					</section>
				{/if}

				{#if selectedRecipe.instructions.length > 0}
					<section class="detail-section">
						<div class="section-title">Instructions</div>
						<ol class="instruction-list">
							{#each selectedRecipe.instructions as step}
								<li class="instruction-item">{step.text}</li>
							{/each}
						</ol>
					</section>
				{/if}
			</article>
		{:else}
			<div class="empty-state">
				<p class="muted">{recipes.length ? 'Select a recipe.' : 'No recipes yet. Use + in the sidebar to create one.'}</p>
			</div>
		{/if}
	</main>
</div>

<style>
	.recipes-view {
		display: flex;
		height: 100vh;
		overflow: hidden;
	}

	.recipe-content {
		flex: 1;
		overflow-y: auto;
		padding: 1.2rem 1.5rem;
		max-width: 52rem;
	}

	/* ── Form ── */

	.form-actions--bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}

	.form-actions--bar:first-child {
		margin-bottom: 1.25rem;
	}

	.form-actions--bottom {
		margin-top: 1.25rem;
		padding-top: 1rem;
		border-top: 1px solid var(--pico-muted-border-color);
	}

	.form-title {
		font-size: 1.2rem;
		font-weight: 700;
		margin: 0;
	}

	.form-btns {
		display: flex;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.form-body {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.form-section {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	.section-label {
		font-size: 0.68rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		opacity: 0.55;
		margin-bottom: 0.1rem;
	}

	.title-input {
		font-size: 1rem;
		background: transparent;
		border: none;
		border-bottom: 1px solid var(--pico-muted-border-color);
		border-radius: 0;
		padding: 0.3rem 0;
		outline: none;
		color: inherit;
		width: 100%;
	}

	.title-input:focus {
		border-bottom-color: var(--pico-primary);
	}

	.group-block {
		border-left: 2px solid var(--pico-muted-border-color);
		padding-left: 0.6rem;
		margin-bottom: 0.5rem;
	}

	.group-header-row {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		margin-bottom: 0.25rem;
	}

	.group-desc-input {
		flex: 1;
	}

	.ing-form-grid {
		display: grid;
		grid-template-columns: 1fr 5rem 5rem 1.5rem;
		gap: 0.25rem 0.5rem;
		align-items: center;
	}

	.ing-form-header {
		font-size: 0.6rem;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		opacity: 0.5;
		margin-bottom: 0.1rem;
	}

	.bare-input {
		background: transparent;
		border: none;
		border-bottom: 1px solid var(--pico-muted-border-color);
		border-radius: 0;
		padding: 0.2rem 0;
		font-size: 0.85rem;
		outline: none;
		color: inherit;
		width: 100%;
	}

	.bare-input:focus {
		border-bottom-color: var(--pico-primary);
	}

	.amount-input {
		text-align: right;
	}

	.step-row {
		display: flex;
		gap: 0.5rem;
		align-items: flex-start;
		margin-bottom: 0.35rem;
	}

	.step-num {
		font-size: 0.8rem;
		opacity: 0.5;
		padding-top: 0.35rem;
		flex-shrink: 0;
		width: 1.2rem;
		text-align: right;
	}

	.step-textarea {
		flex: 1;
		background: transparent;
		border: 1px solid var(--pico-muted-border-color);
		border-radius: 0.25rem;
		padding: 0.3rem 0.4rem;
		font-size: 0.85rem;
		outline: none;
		color: inherit;
		resize: vertical;
		font-family: inherit;
	}

	.step-textarea:focus {
		border-color: var(--pico-primary);
	}

	.add-link {
		background: none;
		border: none;
		cursor: pointer;
		padding: 0.1rem 0;
		font-size: 0.78rem;
		color: var(--pico-primary);
		opacity: 0.75;
		text-align: left;
		display: inline-block;
	}

	.add-link:hover {
		opacity: 1;
	}

	.icon-btn {
		background: none;
		border: none;
		cursor: pointer;
		padding: 0.1rem 0.2rem;
		opacity: 0.4;
		font-size: 0.75rem;
		flex-shrink: 0;
		color: inherit;
		line-height: 1;
	}

	.icon-btn:hover {
		opacity: 1;
		color: var(--pico-del-color);
	}

	/* ── Detail view ── */

	.detail-header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 0.75rem;
	}

	.recipe-title {
		font-size: 1.5rem;
		font-weight: 700;
		margin: 0;
	}

	.scale-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	.scale-label {
		font-size: 0.72rem;
		opacity: 0.55;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		font-weight: 600;
		white-space: nowrap;
	}

	.scale-select {
		font-size: 0.85rem;
		padding: 0.2rem 0.4rem;
		width: auto;
	}

	.detail-section {
		margin-bottom: 1.5rem;
	}

	.section-title {
		font-size: 0.68rem;
		font-weight: 600;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		opacity: 0.55;
		margin-bottom: 0.4rem;
	}

	/* 3-column ingredient grid: name fills space, amount and unit are fixed */
	.ing-grid {
		display: grid;
		grid-template-columns: 1fr 4.5rem 6rem;
		column-gap: 1rem;
		row-gap: 0.3rem;
		align-items: baseline;
	}

	.col-name {
		font-size: 0.95rem;
	}

	.col-amount {
		text-align: right;
		font-size: 0.9rem;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.col-unit {
		font-size: 0.85rem;
		opacity: 0.7;
		white-space: nowrap;
	}

	.ingredient-group {
		margin-bottom: 0.75rem;
	}

	.group-label {
		font-size: 0.72rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		opacity: 0.55;
		margin-bottom: 0.25rem;
	}

	.instruction-list {
		padding-left: 1.4rem;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
	}

	.instruction-item {
		font-size: 0.95rem;
		line-height: 1.55;
	}

	.muted {
		color: var(--pico-muted-color);
		font-size: 0.9rem;
	}

	.empty-state {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding-top: 1rem;
	}
</style>
