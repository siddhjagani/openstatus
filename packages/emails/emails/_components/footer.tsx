/** @jsxRuntime automatic @jsxImportSource react */

import type * as React from "react";
import { Link, Section, Text } from "react-email";

import { colors, styles } from "./styles";

// Self-hosted branding, read at send time on the server. Assigned to a variable
// first so bundlers (deno bundle / esbuild) don't constant-fold the lookups.
const processEnv: Record<string, string | undefined> =
  typeof process !== "undefined" ? process.env : {};
export const FOOTER_NAME = processEnv.EMAIL_FOOTER_NAME || "Jwero";
export const POSTAL_ADDRESS = processEnv.EMAIL_FOOTER_ADDRESS || "";
const SUPPORT_EMAIL = processEnv.EMAIL_SUPPORT_EMAIL || "";

interface FooterLink {
  label: string;
  href: string;
}

const line = {
  margin: "0 0 6px",
  fontSize: "13px",
  lineHeight: "20px",
  color: colors.muted,
} satisfies React.CSSProperties;

const link = { color: colors.muted, textDecoration: "underline" };

export function Footer({
  reason,
  rule,
  links = [],
}: {
  /** Why the reader got this email. */
  reason?: string;
  /** Alert-rule variant, e.g. "latency > 250ms × 3". */
  rule?: string;
  /** Only pass a link where the page behind it exists. */
  links?: FooterLink[];
}) {
  return (
    <Section style={{ padding: "24px 16px 0", textAlign: "center" }}>
      {rule ? (
        <Text style={line}>
          Alert rule: <span style={styles.mono}>{rule}</span>
        </Text>
      ) : null}
      {reason ? <Text style={line}>{reason}</Text> : null}
      {links.length > 0 ? (
        <Text style={line}>
          {links.map((l, i) => (
            <span key={l.href}>
              {i > 0 ? " · " : null}
              <Link href={l.href} style={link}>
                {l.label}
              </Link>
            </span>
          ))}
        </Text>
      ) : null}
      <Text style={{ ...line, margin: 0, color: colors.faint }}>
        {FOOTER_NAME}
        {POSTAL_ADDRESS ? ` · ${POSTAL_ADDRESS}` : null}
        {SUPPORT_EMAIL ? (
          <>
            {" · "}
            <Link
              href={`mailto:${SUPPORT_EMAIL}`}
              style={{ ...link, color: colors.faint }}
            >
              Support
            </Link>
          </>
        ) : null}
      </Text>
    </Section>
  );
}
