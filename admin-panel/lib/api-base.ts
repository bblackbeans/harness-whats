/** No browser usa proxy same-origin (/backend). No servidor usa URL interna em runtime. */
export function getApiBase(): string {
  if (typeof window !== "undefined") {
    return "/backend";
  }
  const url =
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8787";
  return url.replace(/\/$/, "");
}
