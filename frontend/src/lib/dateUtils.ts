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

export type TimedEventChipContent = {
	compact: boolean;
	narrow: boolean;
	showEndTime: boolean;
	titleLines: number;
	descriptionLines: number;
};

export function plainTextFromHtml(input: string | null | undefined): string {
	if (!input) return '';
	return input
		.replace(/<br\s*\/?>/gi, '\n')
		.replace(/<\/(p|div|li|ul|ol|h[1-6])>/gi, '\n')
		.replace(/<[^>]+>/g, ' ')
		.replace(/&nbsp;/gi, ' ')
		.replace(/&amp;/gi, '&')
		.replace(/&lt;/gi, '<')
		.replace(/&gt;/gi, '>')
		.replace(/[ \t]+\n/g, '\n')
		.replace(/\n[ \t]+/g, '\n')
		.replace(/\n{3,}/g, '\n\n')
		.replace(/[ \t]{2,}/g, ' ')
		.trim();
}

export function timedEventChipContent(
	heightPx: number,
	widthFraction = 1,
	hasDescription = false
): TimedEventChipContent {
	const narrow = widthFraction < 0.44;
	const compact = heightPx < 40;
	const lineHeight = narrow ? 13 : 14;
	const chrome = compact ? 8 : 12;
	const textLines = Math.max(1, Math.floor((heightPx - chrome) / lineHeight));
	const titleMax = narrow ? 4 : 6;

	if (compact) {
		return {
			compact: true,
			narrow,
			showEndTime: widthFraction >= 0.52 && heightPx >= 24,
			titleLines: 1,
			descriptionLines: 0,
		};
	}

	let titleLines = Math.min(titleMax, Math.max(1, textLines - 1));
	let descriptionLines = 0;
	const preferredTitleLines = narrow ? 2 : 3;

	if (hasDescription && textLines >= preferredTitleLines + 2) {
		descriptionLines = Math.max(1, textLines - 1 - preferredTitleLines);
		titleLines = Math.min(
			titleMax,
			Math.max(preferredTitleLines, textLines - 1 - descriptionLines)
		);
	}

	return {
		compact: false,
		narrow,
		showEndTime: widthFraction >= 0.48 && textLines >= 2,
		titleLines,
		descriptionLines,
	};
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
		// Timed events: include on every day they overlap (multi-day spanning)
		const dayStart = startOfDay(day);
		const dayEnd = addDays(dayStart, 1);
		return s.getTime() < dayEnd.getTime() && e.getTime() > dayStart.getTime();
	});
}

// Timed event segments split across midnight and optionally clamped to a view window.
export type TimedSegment = {
	id: string;
	ev: CalendarEvent;
	origStart: Date;
	origEnd: Date;
	start: Date; // actual segment start (clamped to day boundaries)
	end: Date;   // actual segment end (clamped to day boundaries)
	displayStart: Date; // clamped to view start (e.g., 06:00) for rendering
	displayEnd: Date;   // clamped for rendering (may be small window)
	truncatedBefore: boolean; // true if original start is before displayStart
	truncatedAfter: boolean;  // true if original end is after displayEnd
	// New flags
	isContinuation: boolean; // true if this segment is not the event's first segment
	startsAtMidnight: boolean;
	endsAtMidnight: boolean;
	isFullDay: boolean; // covers the whole day (treat as allday)
};

// Use exported helpers `startOfDay` and `addDays` instead of duplicating logic.

/**
 * Split a timed event into per-day segments (clamped at midnight boundaries).
 */
export function splitEventIntoDaySegments(ev: CalendarEvent): { start: Date; end: Date; day: Date }[] {
	const s = eventStart(ev);
	const e = eventEnd(ev);
	const segments: { start: Date; end: Date; day: Date }[] = [];
	let curDay = startOfDay(s);
	// iterate days while curDay < e
	while (curDay.getTime() < e.getTime()) {
		const nextDay = addDays(curDay, 1);
		const segStart = new Date(Math.max(s.getTime(), curDay.getTime()));
		const segEnd = new Date(Math.min(e.getTime(), nextDay.getTime()));
		if (segStart.getTime() < segEnd.getTime()) {
			segments.push({ start: segStart, end: segEnd, day: curDay });
		}
		curDay = nextDay;
	}
	return segments;
}

/**
 * For a given day, produce timed segments suitable for layout and rendering.
 * Segments are clamped to the day's boundaries and to the view start hour (e.g., 6).
 */
export function timedSegmentsForDay(events: CalendarEvent[], day: Date, viewStartHour = 6): TimedSegment[] {
	const viewDayStart = new Date(day.getFullYear(), day.getMonth(), day.getDate(), viewStartHour);
	const dayEnd = new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1);
	const segments: TimedSegment[] = [];
	for (const ev of events) {
		if (isAllDay(ev)) continue;
		for (const seg of splitEventIntoDaySegments(ev)) {
			if (!isSameDay(seg.day, day)) continue;
			const origStart = seg.start;
			const origEnd = seg.end;
			let displayStart = new Date(origStart);
			let displayEnd = new Date(origEnd);
			let truncatedBefore = false;
			let truncatedAfter = false;

			// If the event segment ends before the view start, collapse it to a small window at viewStartHour
			if (origEnd.getTime() <= viewDayStart.getTime()) {
				truncatedBefore = true;
				displayStart = new Date(viewDayStart);
				displayEnd = new Date(viewDayStart.getTime() + 15 * 60 * 1000); // 15 minutes display
			} else {
				// If the segment starts before view start, clamp display start to view start and mark truncated
				if (origStart.getTime() < viewDayStart.getTime()) {
					truncatedBefore = true;
					displayStart = new Date(viewDayStart);
				}
				// If the segment ends after day end (shouldn't happen here) clamp and mark truncatedAfter
				if (origEnd.getTime() > dayEnd.getTime()) {
					truncatedAfter = true;
					displayEnd = new Date(dayEnd);
				}
			}

			const id = `${ev.id}::${localDateStr(day)}`;
			const evStart = eventStart(ev);
			const startsAtMidnight = origStart.getTime() === startOfDay(day).getTime();
			const endsAtMidnight = origEnd.getTime() === dayEnd.getTime();
			const isContinuation = evStart.getTime() < origStart.getTime();
			// Treat any segment that covers the whole day as full-day (covers middle days).
			const isFullDay = origStart.getTime() <= startOfDay(day).getTime() && origEnd.getTime() >= dayEnd.getTime();
			segments.push({
				id,
				ev,
				origStart,
				origEnd,
				start: origStart,
				end: origEnd,
				displayStart,
				displayEnd,
				truncatedBefore,
				truncatedAfter,
				isContinuation,
				startsAtMidnight,
				endsAtMidnight,
				isFullDay,
			});
		}
	}
	return segments;
}

/**
 * Layout overlapping segments (same API as layoutOverlappingTimedEvents but for TimedSegment)
 */
export function layoutOverlappingSegments(segments: TimedSegment[]): Map<string, EventLayout> {
	const sorted = [...segments].sort((a, b) => {
		const ds = a.displayStart.getTime() - b.displayStart.getTime();
		if (ds !== 0) return ds;
		return (b.displayEnd.getTime() - b.displayStart.getTime()) - (a.displayEnd.getTime() - a.displayStart.getTime());
	});

	const result = new Map<string, EventLayout>();

	let cluster: TimedSegment[] = [];
	let clusterEnd = -Infinity;

	function flush() {
		if (!cluster.length) return;
		const colEnds: number[] = [];
		const colById = new Map<string, number>();
		for (const s of cluster) {
			const st = s.displayStart.getTime();
			const en = s.displayEnd.getTime();
			let col = colEnds.findIndex((end) => end <= st);
			if (col === -1) {
				col = colEnds.length;
				colEnds.push(en);
			} else {
				colEnds[col] = en;
			}
			colById.set(s.id, col);
		}
		const cols = colEnds.length || 1;
		for (const s of cluster) {
			const col = colById.get(s.id) ?? 0;
			const width = 1 / cols;
			result.set(s.id, { col, cols, left: col * width, width });
		}
		cluster = [];
		clusterEnd = -Infinity;
	}

	for (const s of sorted) {
		const st = s.displayStart.getTime();
		const en = s.displayEnd.getTime();
		if (cluster.length === 0) {
			cluster = [s];
			clusterEnd = en;
			continue;
		}
		if (st >= clusterEnd) {
			flush();
			cluster = [s];
			clusterEnd = en;
			continue;
		}
		cluster.push(s);
		clusterEnd = Math.max(clusterEnd, en);
	}
	flush();
	return result;
}

// ---- Overlap layout (Day/Week timed events) ----

export type EventLayout = {
	left: number;  // 0..1	
	width: number; // 0..1
	col: number;
	cols: number;
};

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
