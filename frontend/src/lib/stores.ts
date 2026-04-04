import { writable } from 'svelte/store';

export type View = 'day' | 'week' | 'month' | 'weather' | 'todo';

export const VALID_VIEWS: View[] = ['day', 'week', 'month', 'weather', 'todo'];

export const currentView = writable<View>('week');
