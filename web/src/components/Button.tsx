// Copyright (c) 2026 Document Review Contributors
// SPDX-License-Identifier: MIT

import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  children: ReactNode;
};

export function Button({ variant = "secondary", className = "", ...props }: ButtonProps) {
  return <button className={`button button-${variant} ${className}`} {...props} />;
}
