/**
 * Copyright 2025 IBM Corp.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import Link from "next/link";
import { notFound } from "next/navigation";
import { MDXRemote } from "next-mdx-remote/rsc";
import remarkGfm from "remark-gfm";
import rehypePrettyCode from "rehype-pretty-code";
import {
  getAllPages,
  getPage,
  getPageTitle,
  getNavGroups,
  extractHeadings,
  getAdjacentPages,
} from "@/lib/docs";
import { mintlifyComponents } from "@/components/mintlify";
import { TableOfContents } from "@/components/toc";
import { ThemeToggle } from "@/components/theme-toggle";
import { MobileMenuButton } from "@/components/mobile-menu";

export function generateStaticParams() {
  return getAllPages()
    .filter(({ version }) => version === "stable" || version === "development")
    .map(({ version, slug }) => ({
      version,
      slug,
    }));
}

function Sidebar({
  version,
  currentSlug,
}: {
  version: string;
  currentSlug: string;
}) {
  const groups = getNavGroups(version);

  return (
    <nav className="sidebar">
      <div className="sidebar-header">
        <span>Kagenti ADK</span>
        <ThemeToggle />
      </div>
      {groups.map((group) => (
        <div key={group.group}>
          <div className="nav-group-title">{group.group}</div>
          {group.pages.map((page) => {
            if (typeof page !== "string") return null;
            const parts = page.split("/");
            const slug = parts.slice(1).join("/");
            const label = getPageTitle(page);
            return (
              <Link
                key={page}
                href={`/${page}`}
                className={`nav-link${slug === currentSlug ? " active" : ""}`}
              >
                {label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export default async function DocPage({
  params,
}: {
  params: Promise<{ version: string; slug: string[] }>;
}) {
  const { version, slug } = await params;
  const page = getPage(version, slug);

  if (!page) {
    notFound();
  }

  // Strip embedme comments and HTML style string attributes (MDX requires object syntax)
  const cleanContent = page.content
    .replace(/\{\/\*\s*<!--\s*embedme\s+[^>]+-->\s*\*\/\}/g, "")
    .replace(/\sstyle="[^"]*"/g, "");

  const headings = extractHeadings(cleanContent);
  const { prev, next } = getAdjacentPages(version, slug);

  return (
    <div className="layout">
      <Sidebar version={version} currentSlug={slug.join("/")} />
      <MobileMenuButton />
      <main className="main-content">
        <h1 className="page-title">{page.title}</h1>
        {page.description && (
          <p className="page-description">{page.description}</p>
        )}
        <div className="prose">
          <MDXRemote
            source={cleanContent}
            components={mintlifyComponents}
            options={{
              mdxOptions: {
                remarkPlugins: [remarkGfm],
                rehypePlugins: [
                  [
                    rehypePrettyCode,
                    {
                      theme: {
                        dark: "github-dark",
                        light: "github-light",
                      },
                      keepBackground: false,
                    },
                  ],
                ],
              },
            }}
          />
        </div>

        {(prev || next) && (
          <nav className="page-nav">
            {prev ? (
              <Link href={prev.href} className="page-nav-link page-nav-prev">
                <span className="page-nav-label">Previous</span>
                <span className="page-nav-title">{prev.title}</span>
              </Link>
            ) : (
              <div />
            )}
            {next ? (
              <Link href={next.href} className="page-nav-link page-nav-next">
                <span className="page-nav-label">Next</span>
                <span className="page-nav-title">{next.title}</span>
              </Link>
            ) : (
              <div />
            )}
          </nav>
        )}
      </main>
      <TableOfContents headings={headings} />
    </div>
  );
}
