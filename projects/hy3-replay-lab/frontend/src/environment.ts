export function clearedHy3EnvironmentValues(
  source: Record<string, string | undefined>,
): Record<string, string> {
  return Object.fromEntries(
    Object.keys(source)
      .filter((key) => key.toLocaleLowerCase() === "hy3" || key.toLocaleLowerCase().startsWith("hy3_"))
      .map((key) => [key, ""]),
  );
}
