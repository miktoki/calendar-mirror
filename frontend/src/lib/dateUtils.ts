import type { CalendarEvent } from './api';

/** Parse a date string as local time.
 *  date-only strings like "2026-04-18" are treated as local midnight,
 *  not UTC midnight (which is what `new Date("2026-04-18")` gives). */
function parseLocal(s: string): Date {
	// If it's a date-only string (no T), parse as local midnight.
	if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
		const [y, m, d] = s.split('-').map(Number);
		return new Date(y, m - 1, d);
	}
	return new Date(s);
}

export function eventStart(ev: CalendarEvent): Date {
	return parseLocal(ev.start.dateTime ?? ev.start.date ?? '');
}

export function eventEnd(ev: CalendarEvent): Date {
	return parseLocal(ev.end.dateTime ?? ev.end.date ?? '');
}

export function isAllDay(ev: CalendarEvent): boolean {
	return !ev.start.dateTime;
}

/** Format a Date as "YYYY-MM-DD" in local time. */
export function localDateStr(d: Date): string {
	const y = d.getFullYear();
	const m = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${y}-${m}-${day}`;
}

/**
 * Returns the day key used by `weatherByDay` for a given *local* calendar day.
 *
 * The weather data is bucketed by UTC day (`YYYY-MM-DD`). To map a local day
 * cell to the correct UTC bucket (without local-midnight shifting into the
 * previous UTC day), we compute the key from local noon.
 */
export function weatherDayKeyForLocalDay(d: Date): string {
	const noonLocal = new Date(d.getFullYear(), d.getMonth(), d.getDate(), 12);
	const y = noonLocal.getUTCFullYear();
	const m = String(noonLocal.getUTCMonth() + 1).padStart(2, '0');
	const day = String(noonLocal.getUTCDate()).padStart(2, '0');
	return `${y}-${m}-${day}`;
}

export function startOfDay(d: Date): Date {
	return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function startOfWeek(d: Date): Date {
	const day = d.getDay();
	const diff = (day === 0 ? -6 : 1 - day);
	const result = startOfDay(d);
	result.setDate(result.getDate() + diff);
	return result;
}

export function startOfMonth(d: Date): Date {
	return new Date(d.getFullYear(), d.getMonth(), 1);
}

export function addDays(d: Date, n: number): Date {
	const r = new Date(d);
	r.setDate(r.getDate() + n);
	return r;
}

export function addMonths(d: Date, n: number): Date {
	const r = new Date(d.getFullYear(), d.getMonth() + n, 1);
	// Clamp to the last day of the target month so e.g. Jan 31 + 1 month = Feb 28
	const lastDay = new Date(r.getFullYear(), r.getMonth() + 1, 0).getDate();
	r.setDate(Math.min(d.getDate(), lastDay));
	return r;
}

export function isSameDay(a: Date, b: Date): boolean {
	return (
		a.getFullYear() === b.getFullYear() &&
		a.getMonth() === b.getMonth() &&
		a.getDate() === b.getDate()
	);
}

export function formatTime(d: Date): string {
	return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
}

export function formatDate(d: Date): string {
	return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
}

export function formatMonthYear(d: Date): string {
	return d.toLocaleDateString([], { month: 'long', year: 'numeric' });
}

export function isoWeekNumber(d: Date): number {
	const tmp = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
	tmp.setUTCDate(tmp.getUTCDate() + 4 - (tmp.getUTCDay() || 7));
	const yearStart = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 1));
	return Math.ceil(((tmp.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

export function eventsOnDay(events: CalendarEvent[], day: Date): CalendarEvent[] {
	const dayStr = localDateStr(day);
	return events.filter((ev) => {
		const s = eventStart(ev);
		const e = eventEnd(ev);
		if (isAllDay(ev)) {
			const startStr = (ev.start.date ?? localDateStr(s)).slice(0, 10);
			const endStr = (ev.end.date ?? localDateStr(e)).slice(0, 10);
			return dayStr >= startStr && dayStr < endStr;
		}
		return isSameDay(s, day);
	});
}

// ---- Overlap layout (Day/Week timed events) ----

export type EventLayout = {
	left: number;  // 0..1
	width: number; // 0..1
	col: number;
	cols: number;
};

function overlaps(a: CalendarEvent, b: CalendarEvent): boolean {
	const as = eventStart(a).getTime();
	const ae = eventEnd(a).getTime();
	const bs = eventStart(b).getTime();
	const be = eventEnd(b).getTime();
	return as < be && bs < ae;
}

/**
 * Given a list of timed events (same day/column), assign each event a column within its
 * overlap cluster so that overlapping events can be rendered side-by-side.
 */
export function layoutOverlappingTimedEvents(events: CalendarEvent[]): Map<string, EventLayout> {
	// Sort by start asc, then duration desc.
	const sorted = [...events].sort((a, b) => {
		const ds = eventStart(a).getTime() - eventStart(b).getTime();
		if (ds !== 0) return ds;
		return eventEnd(b).getTime() - eventEnd(a).getTime();
	});

	const result = new Map<string, EventLayout>();

	let clusterEvents: CalendarEvent[] = [];
	let clusterEnd = -Infinity;

	function flushCluster() {
		if (!clusterEvents.length) return;
		// Greedy column assignment within cluster.
		const colEnds: number[] = [];
		const colById = new Map<string, number>();

		for (const ev of clusterEvents) {
			const s = eventStart(ev).getTime();
			const e = eventEnd(ev).getTime();
			let col = colEnds.findIndex((end) => end <= s);
			if (col === -1) {
				col = colEnds.length;
				colEnds.push(e);
			} else {
				colEnds[col] = e;
			}
			colById.set(ev.id, col);
		}

		const cols = colEnds.length || 1;
		for (const ev of clusterEvents) {
			const col = colById.get(ev.id) ?? 0;
			const width = 1 / cols;
			result.set(ev.id, {
				col,
				cols,
				left: col * width,
				width,
			});
		}

		clusterEvents = [];
		clusterEnd = -Infinity;
	}

	for (const ev of sorted) {
		const s = eventStart(ev).getTime();
		const e = eventEnd(ev).getTime();
		if (clusterEvents.length === 0) {
			clusterEvents = [ev];
			clusterEnd = e;
			continue;
		}
		if (s >= clusterEnd) {
			flushCluster();
			clusterEvents = [ev];
			clusterEnd = e;
			continue;
		}
		clusterEvents.push(ev);
		clusterEnd = Math.max(clusterEnd, e);
	}
	flushCluster();

	return result;
}
