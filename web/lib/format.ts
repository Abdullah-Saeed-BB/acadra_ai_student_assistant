const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/**
 * Render a calendar-day string (`YYYY-MM-DD`) as `Tue 20 Oct`.
 *
 * Days in the planning API are plain calendar dates, not instants, so the parts
 * are read directly and formatted in UTC. Parsing them with `new Date(iso)`
 * would shift the day backwards for readers west of Greenwich.
 */
export function formatDay(iso: string | null | undefined): string {
  if (!iso) return "Backlog";

  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return iso;

  const [, year, month, day] = match;
  const date = new Date(
    Date.UTC(Number(year), Number(month) - 1, Number(day)),
  );
  if (Number.isNaN(date.getTime())) return iso;

  return `${WEEKDAYS[date.getUTCDay()]} ${Number(day)} ${
    MONTHS[Number(month) - 1] ?? month
  }`;
}
