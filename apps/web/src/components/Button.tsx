import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "primary" | "ghost";
};

const VARIANT_CLASS = { default: "", primary: " pri", ghost: " ghost" };

export default function Button({ variant = "default", className = "", type = "button", ...rest }: Props) {
  return <button type={type} className={`btn${VARIANT_CLASS[variant]} ${className}`.trim()} {...rest} />;
}
