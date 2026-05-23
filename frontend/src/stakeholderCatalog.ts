export type StakeholderOption = {
  value: string;
  label: string;
  group: string;
  ordinal?: string;
};

const ACRONYMS = new Set(["ai", "cro", "ehds", "gdpr", "hda", "sme", "wp"]);

function titleCaseToken(token: string): string {
  const lower = token.toLowerCase();
  if (ACRONYMS.has(lower)) return lower.toUpperCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

export function formatStakeholderGroup(value: string): string {
  const base = value.trim().replace(/-\d+$/, "");
  if (!base) return "Unknown stakeholder";
  const words = base
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((token, index) => {
      const lower = token.toLowerCase();
      if (ACRONYMS.has(lower)) return lower.toUpperCase();
      if (index === 0) return titleCaseToken(token);
      return lower;
    });
  return words.join(" ");
}

export function formatStakeholderLabel(value: string): string {
  const trimmed = value.trim();
  const match = trimmed.match(/^(.*?)-(\d+)$/);
  if (!match) return formatStakeholderGroup(trimmed);
  return `${formatStakeholderGroup(match[1])} #${match[2]}`;
}

export function buildStakeholderOptions(values: string[]): StakeholderOption[] {
  return values
    .map((value) => value.trim())
    .filter(Boolean)
    .map((value) => {
      const ordinal = value.match(/-(\d+)$/)?.[1];
      return {
        value,
        label: formatStakeholderLabel(value),
        group: formatStakeholderGroup(value),
        ordinal,
      };
    });
}

export function filterStakeholderOptions(
  options: StakeholderOption[],
  query: string,
  limit = 80,
): StakeholderOption[] {
  const normalized = query.trim().toLowerCase();
  const filtered = normalized
    ? options.filter((option) => (
        option.value.toLowerCase().includes(normalized)
        || option.label.toLowerCase().includes(normalized)
        || option.group.toLowerCase().includes(normalized)
      ))
    : options;
  return filtered.slice(0, limit);
}

export function formatStakeholderLoadedCopy(options: StakeholderOption[]): string {
  const profileCount = options.length;
  const categoryCount = new Set(options.map((option) => option.group)).size;
  if (!profileCount) return "No WP2 stakeholder profiles loaded yet.";
  const profileWord = profileCount === 1 ? "profile" : "profiles";
  const categoryWord = categoryCount === 1 ? "category" : "categories";
  return `${profileCount} WP2 mock stakeholder ${profileWord} loaded across ${categoryCount} ${categoryWord}.`;
}
