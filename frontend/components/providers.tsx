"use client";

import { ThemeProvider } from "next-themes";
import { SettingsProvider } from "@/lib/settings";
import { ConsoleStoreProvider } from "@/lib/store";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <SettingsProvider>
        <ConsoleStoreProvider>{children}</ConsoleStoreProvider>
      </SettingsProvider>
    </ThemeProvider>
  );
}
