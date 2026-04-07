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

import React from "react";
import Link from "next/link";
import { PreBlock } from "./pre-block";

function Callout({
  type,
  children,
}: {
  type: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`callout callout-${type}`}>
      <div className="callout-content">{children}</div>
    </div>
  );
}

export function Tip({ children }: { children: React.ReactNode }) {
  return <Callout type="tip">{children}</Callout>;
}

export function Warning({ children }: { children: React.ReactNode }) {
  return <Callout type="warning">{children}</Callout>;
}

export function Note({ children }: { children: React.ReactNode }) {
  return <Callout type="note">{children}</Callout>;
}

export function Info({ children }: { children: React.ReactNode }) {
  return <Callout type="info">{children}</Callout>;
}

export function Danger({ children }: { children: React.ReactNode }) {
  return <Callout type="warning">{children}</Callout>;
}

export function Steps({
  children,
  title,
}: {
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <div className="steps">
      {title && <h3 className="steps-title">{title}</h3>}
      <div className="steps-list">{children}</div>
    </div>
  );
}

export function Step({
  children,
  title,
}: {
  children: React.ReactNode;
  title: string;
}) {
  return (
    <div className="step">
      <div className="step-title">{title}</div>
      <div className="step-content">{children}</div>
    </div>
  );
}

export function CardGroup({
  children,
  cols = 2,
}: {
  children: React.ReactNode;
  cols?: number;
}) {
  return (
    <div
      className="card-group"
      style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
    >
      {children}
    </div>
  );
}

export function Card({
  children,
  title,
  href,
}: {
  children: React.ReactNode;
  title: string;
  icon?: string;
  href?: string;
}) {
  const content = (
    <div className="card">
      <div className="card-title">{title}</div>
      <div className="card-content">{children}</div>
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }
  return content;
}

export function Tabs({ children }: { children: React.ReactNode }) {
  return <div className="tabs">{children}</div>;
}

export function Tab({
  children,
  title,
}: {
  children: React.ReactNode;
  title: string;
}) {
  return (
    <details className="tab">
      <summary>{title}</summary>
      <div className="tab-content">{children}</div>
    </details>
  );
}

export function Accordion({
  children,
  title,
}: {
  children: React.ReactNode;
  title: string;
}) {
  return (
    <details className="accordion">
      <summary>{title}</summary>
      <div className="accordion-content">{children}</div>
    </details>
  );
}

export function CodeGroup({ children }: { children: React.ReactNode }) {
  return <div className="code-group">{children}</div>;
}

export function ApiResult({ children }: { children: React.ReactNode }) {
  return <div className="api-result">{children}</div>;
}

function MdxLink(props: React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  const href = props.href ?? "";
  if (href.startsWith("/") || href.startsWith("./") || href.startsWith("../")) {
    return <Link {...props} href={href} />;
  }
  return <a {...props} />;
}

export const mintlifyComponents = {
  pre: PreBlock,
  a: MdxLink,
  Tip,
  Warning,
  Note,
  Info,
  Danger,
  Steps,
  Step,
  CardGroup,
  Card,
  Tabs,
  Tab,
  Accordion,
  CodeGroup,
  ApiResult,
};
