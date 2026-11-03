/** Keep identical repeats without tying distinct content to its list position. */
export function withContentKeys<T>(items: readonly T[], content: (item: T) => string) {
  const occurrences = new Map<string, number>();
  return items.map(item => {
    const value = content(item);
    const occurrence = occurrences.get(value) || 0;
    occurrences.set(value, occurrence + 1);
    return { item, key: JSON.stringify([value, occurrence]) };
  });
}
