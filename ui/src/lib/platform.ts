export const IS_DESKTOP = process.env.NEXT_PUBLIC_PLATFORM === "tauri";

const LOCAL_API = "http://127.0.0.1:8765";

export function resolveApiBaseUrl(): string {
  if (IS_DESKTOP) return LOCAL_API;
  if (typeof window !== "undefined" && window.location.hostname === "localhost") {
    return LOCAL_API;
  }
  return "";
}
