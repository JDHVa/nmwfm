import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "@/App";
import { initBackend } from "@/lib/backend";
import "@/index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 2, retryDelay: 1000, refetchOnWindowFocus: false, staleTime: 5_000 } },
});

initBackend()
  .catch(() => undefined)
  .then(() => {
    createRoot(document.getElementById("root")!).render(
      <StrictMode>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </StrictMode>,
    );
  });
