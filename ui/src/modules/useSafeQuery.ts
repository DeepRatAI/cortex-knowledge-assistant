import { useCallback } from "react";
import {
  queryBackend,
  queryBackendStream,
  QueryOptions,
} from "../services/api";
import { useAuth } from "./AuthContext";

/**
 * Small helper hook to call the backend and handle auth failures consistently.
 *
 * Any 401 from the API will trigger a logout and surface a clear
 * "session expired" style error message to the caller.
 */
export function useSafeQuery() {
  const { logout } = useAuth();

  const ask = useCallback(
    async (question: string, options: QueryOptions = {}) => {
      try {
        return await queryBackend(question, options);
      } catch (err: any) {
        const message: string = err?.message ?? "Error inesperado";

        // queryBackend currently throws errors of the form
        // `Error <status>: <body>`. We parse the status code to detect 401.
        const match = message.match(/^Error\s+(\d{3})/);
        const status = match ? Number(match[1]) : undefined;

        if (status === 401) {
          // Clear local auth state so the app returns to the login screen.
          logout();
          throw new Error(
            "Tu sesión ha expirado o es inválida. Inicia sesión de nuevo."
          );
        }

        throw err;
      }
    },
    [logout]
  );

  const askStream = useCallback(
    async (
      question: string,
      options: QueryOptions = {},
      onToken: (token: string) => void,
      onDone?: () => void,
      onError?: (error: string) => void
    ) => {
      try {
        await queryBackendStream(question, options, onToken, onDone, onError);
      } catch (err: any) {
        const message: string = err?.message ?? "Error inesperado";
        const match = message.match(/^Error\s+(\d{3})/);
        const status = match ? Number(match[1]) : undefined;

        if (status === 401) {
          logout();
          throw new Error(
            "Tu sesión ha expirado o es inválida. Inicia sesión de nuevo."
          );
        }

        throw err;
      }
    },
    [logout]
  );

  return { ask, askStream };
}
