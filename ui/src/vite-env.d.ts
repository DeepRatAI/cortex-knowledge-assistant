/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEMO_DOMAIN: "banking" | "university" | "clinic";
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
