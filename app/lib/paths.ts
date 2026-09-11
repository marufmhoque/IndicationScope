// Next's basePath prefixes assets, <Link> and router navigation — but NOT fetch().
// An unprefixed API call resolves against the domain root, where the portfolio
// proxies nothing, so it 404s. Every fetch to the Python API must go through this.
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export function apiUrl(path: string): string {
  return `${BASE_PATH}${path}`;
}
