import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { LandingPage } from "@/components/landing/landing-page";

export const metadata: Metadata = {
  title: { absolute: "Lumiant | Inventory intelligence you can check" },
  description:
    "Lumiant connects read-only to your ERP data, builds one trusted inventory model and answers in plain language, with the source of every number.",
};

/** Public landing page. Signed-in users (development session cookie) go straight to the app. */
export default async function Home() {
  const oidc = (process.env.LUMIANT_AUTH_MODE ?? "dev").toLowerCase() === "oidc";
  if (!oidc && (await cookies()).has("lumiant_session")) redirect("/overview");
  return <LandingPage signInHref={oidc ? "/overview" : "/login"} />;
}
