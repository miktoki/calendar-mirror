const BASE = import.meta.env.VITE_API_BASE ?? '';

export interface CalendarEvent {
	id: string;
	summary: string;
	description?: string;
	location?: string;
	colorId?: string;
	calendarColor?: string;
	calendarForeground?: string;
	start: { dateTime?: string; date?: string; timeZone?: string };
	end: { dateTime?: string; date?: string; timeZone?: string };
	allDay?: boolean;
}

const EVENT_COLORS: Record<string, { bg: string; fg: string }> = {
	'1':  { bg: '#a4bdfc', fg: '#1a1a2e' },
	'2':  { bg: '#7ae7bf', fg: '#1a1a2e' },
	'3':  { bg: '#dbadff', fg: '#1a1a2e' },
	'4':  { bg: '#ff887c', fg: '#1a1a2e' },
	'5':  { bg: '#fbd75b', fg: '#1a1a2e' },
	'6':  { bg: '#ffb878', fg: '#1a1a2e' },
	'7':  { bg: '#46d6db', fg: '#1a1a2e' },
	'8':  { bg: '#e1e1e1', fg: '#1a1a2e' },
	'9':  { bg: '#5484ed', fg: '#ffffff' },
	'10': { bg: '#51b749', fg: '#ffffff' },
	'11': { bg: '#dc2127', fg: '#ffffff' },
};

const DEFAULT_COLOR = { bg: 'var(--pico-primary-background)', fg: 'var(--pico-primary-inverse)' };

export function eventColor(ev: CalendarEvent): { bg: string; fg: string } {
	// Prefer the event colour first to keep the original Google Calendar palette.
	if (ev.colorId && EVENT_COLORS[ev.colorId]) return EVENT_COLORS[ev.colorId];
	if (ev.calendarColor) {
		return { bg: ev.calendarColor, fg: ev.calendarForeground ?? '#ffffff' };
	}
	return DEFAULT_COLOR;
}

export interface WeatherRecord {
	fetched_at: string;
	forecast: MetForecast;
}

export interface MetForecast {
	properties: {
		timeseries: TimeSeries[];
	};
}

export interface TimeSeries {
	time: string;
	data: {
		instant: { details: Record<string, number> };
		next_1_hours?: { summary: { symbol_code: string }; details: Record<string, number> };
		next_6_hours?: { summary: { symbol_code: string }; details: Record<string, number> };
		next_12_hours?: { summary: { symbol_code: string }; details: Record<string, number> };
	};
}

export interface TodoList {
	id: number;
	name: string;
	list_type?: 'todo' | 'counter';
	reset_kind?: 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly';
	week_ends_on?: number;
	counter_mode?: 'normal' | 'negative';
	counter_initial?: number;
	created_at: string;
}

export interface TodoItem {
	id: number;
	list_id: number;
	text: string;
	done: number;
	checked_at?: string | null;
	sort_order: number;
	created_at: string;
}

export interface CounterState {
	counter_id: number;
	reset_kind: 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly';
	week_ends_on: number;
	mode: 'normal' | 'negative';
	initial: number;
	value: number;
	today: number;
}

async function readJsonOrThrow<T>(res: Response, context: string): Promise<T> {
	const contentType = res.headers.get('content-type') ?? '';
	if (!res.ok) {
		const body = await res.text().catch(() => '');
		const snippet = body.slice(0, 200).replace(/\s+/g, ' ').trim();
		throw new Error(`${context}: ${res.status} ${res.statusText}${snippet ? ` — ${snippet}` : ''}`);
	}
	if (!contentType.includes('application/json')) {
		const body = await res.text().catch(() => '');
		const snippet = body.slice(0, 200).replace(/\s+/g, ' ').trim();
		throw new Error(`${context}: expected JSON but got '${contentType || 'unknown'}'${snippet ? ` — ${snippet}` : ''}`);
	}
	return res.json() as Promise<T>;
}

export async function fetchEvents(min?: Date, max?: Date, signal?: AbortSignal): Promise<CalendarEvent[]> {
	const url = new URL(`${BASE}/api/events`, window.location.href);
	if (min) url.searchParams.set('min', min.toISOString());
	if (max) url.searchParams.set('max', max.toISOString());
	const res = await fetch(url.toString(), { signal });
	return readJsonOrThrow<CalendarEvent[]>(res, 'Failed to fetch events');
}

export async function fetchWeather(): Promise<WeatherRecord> {
	const res = await fetch(`${BASE}/api/weather`);
	return readJsonOrThrow<WeatherRecord>(res, 'Failed to fetch weather');
}

export async function refreshWeather(): Promise<void> {
	const res = await fetch(`${BASE}/api/weather/refresh`, { method: 'POST' });
	if (!res.ok) throw new Error(`Failed to refresh weather: ${res.status}`);
}

export async function fetchLists(): Promise<TodoList[]> {
	const res = await fetch(`${BASE}/api/lists`);
	return readJsonOrThrow<TodoList[]>(res, 'Failed to fetch lists');
}

export async function createList(body: {
	name: string;
	list_type?: 'todo' | 'counter';
	reset_kind?: 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly';
	week_ends_on?: number;
	counter_mode?: 'normal' | 'negative';
	counter_initial?: number;
}): Promise<TodoList> {
	const res = await fetch(`${BASE}/api/lists`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});
	return readJsonOrThrow<TodoList>(res, 'Failed to create list');
	}

export async function fetchCounter(counterId: number): Promise<CounterState> {
	const res = await fetch(`${BASE}/api/counters/${counterId}`);
	return readJsonOrThrow<CounterState>(res, 'Failed to fetch counter');
	}

export async function incCounter(counterId: number, delta: number): Promise<{ ok: boolean; value: number; today: number }> {
	const res = await fetch(`${BASE}/api/counters/${counterId}/inc`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ delta })
	});
	return readJsonOrThrow<{ ok: boolean; value: number; today: number }>(res, 'Failed to update counter');
}

export async function deleteList(id: number): Promise<void> {
	const res = await fetch(`${BASE}/api/lists/${id}`, { method: 'DELETE' });
	if (!res.ok) throw new Error(`Failed to delete list: ${res.status}`);
}

export async function fetchItems(listId: number): Promise<TodoItem[]> {
	const res = await fetch(`${BASE}/api/lists/${listId}/items`);
	return readJsonOrThrow<TodoItem[]>(res, 'Failed to fetch items');
}

export async function createItem(listId: number, text: string): Promise<TodoItem> {
	const res = await fetch(`${BASE}/api/lists/${listId}/items`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ text }),
	});
	return readJsonOrThrow<TodoItem>(res, 'Failed to create item');
}

export async function patchItem(id: number, patch: { text?: string; done?: boolean }): Promise<void> {
	const res = await fetch(`${BASE}/api/items/${id}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(patch),
	});
	if (!res.ok) throw new Error(`Failed to update item: ${res.status}`);
}

export async function deleteItem(id: number): Promise<void> {
	const res = await fetch(`${BASE}/api/items/${id}`, { method: 'DELETE' });
	if (!res.ok) throw new Error(`Failed to delete item: ${res.status}`);
}
