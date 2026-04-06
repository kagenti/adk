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

import fs from "fs";
import path from "path";
import matter from "gray-matter";

const DOCS_ROOT = path.join(process.cwd(), "..", "..", "docs");

export interface DocPage {
  version: string;
  slug: string[];
  title: string;
  description: string;
  content: string;
}

export interface NavGroup {
  group: string;
  pages: (string | { group: string; openapi: string })[];
}

export interface NavVersion {
  version: string;
  groups: NavGroup[];
}

export function getNavigation(): NavVersion[] {
  const docsJson = JSON.parse(
    fs.readFileSync(path.join(DOCS_ROOT, "docs.json"), "utf-8"),
  );
  return docsJson.navigation.versions;
}

export function getAllPages(): { version: string; slug: string[] }[] {
  const nav = getNavigation();
  const pages: { version: string; slug: string[] }[] = [];

  for (const ver of nav) {
    for (const group of ver.groups) {
      for (const page of group.pages) {
        if (typeof page === "string") {
          const parts = page.split("/");
          const version = parts[0];
          const slug = parts.slice(1);
          pages.push({ version, slug });
        }
      }
    }
  }

  return pages;
}

export function getPage(version: string, slug: string[]): DocPage | null {
  const filePath = path.join(DOCS_ROOT, version, ...slug) + ".mdx";

  if (!fs.existsSync(filePath)) {
    return null;
  }

  const raw = fs.readFileSync(filePath, "utf-8");
  const { data, content } = matter(raw);

  return {
    version,
    slug,
    title: (data.title as string) || slug[slug.length - 1],
    description: (data.description as string) || "",
    content,
  };
}

export function getNavGroups(version: string): NavGroup[] {
  const nav = getNavigation();
  const ver = nav.find((v) => v.version === version);
  return ver?.groups || [];
}

export function getPageTitle(pagePath: string): string {
  const filePath = path.join(DOCS_ROOT, pagePath) + ".mdx";
  if (!fs.existsSync(filePath)) {
    const parts = pagePath.split("/");
    return parts[parts.length - 1]
      .replace(/-/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }
  const raw = fs.readFileSync(filePath, "utf-8");
  const { data } = matter(raw);
  if (data.title) return data.title as string;
  const parts = pagePath.split("/");
  return parts[parts.length - 1]
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export interface Heading {
  level: 2 | 3;
  text: string;
  id: string;
}

export function extractHeadings(content: string): Heading[] {
  const headings: Heading[] = [];
  const regex = /^(#{2,3})\s+(.+)$/gm;
  let match;
  while ((match = regex.exec(content)) !== null) {
    const text = match[2].replace(/`/g, "").trim();
    const id = text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
    headings.push({
      level: match[1].length as 2 | 3,
      text,
      id,
    });
  }
  return headings;
}

export interface AdjacentPage {
  title: string;
  href: string;
}

export function getAdjacentPages(
  version: string,
  slug: string[],
): { prev: AdjacentPage | null; next: AdjacentPage | null } {
  const groups = getNavGroups(version);
  const allPages: string[] = [];

  for (const group of groups) {
    for (const page of group.pages) {
      if (typeof page === "string") {
        allPages.push(page);
      }
    }
  }

  const currentPath = `${version}/${slug.join("/")}`;
  const idx = allPages.indexOf(currentPath);

  const toAdjacentPage = (pagePath: string): AdjacentPage => {
    return { title: getPageTitle(pagePath), href: `/${pagePath}` };
  };

  return {
    prev: idx > 0 ? toAdjacentPage(allPages[idx - 1]) : null,
    next: idx < allPages.length - 1 ? toAdjacentPage(allPages[idx + 1]) : null,
  };
}
