/**
 * Acadra lockup: the app icon mark plus the lowercase `acadra` wordmark.
 *
 * The mark is `app/icon.png`, the brand app icon (the waypoint A on the ink field).
 * Keeping one asset means the sidebar, the favicon, and the app icon can never drift.
 * Next.js serves `app/icon.png` as the favicon and it stays importable as an image.
 */
import Image from "next/image";
import icon from "@/app/icon.png";

type MarkProps = {
  size?: number;
  className?: string;
  title?: string;
};

export function AcadraMark({ size = 28, className, title }: MarkProps) {
  return (
    <Image
      src={icon}
      alt={title ?? ""}
      aria-hidden={title ? undefined : true}
      className={className}
      width={size}
      height={size}
      priority
    />
  );
}

export function AcadraLogo({ className }: { className?: string }) {
  return (
    <span className={className ? `brand ${className}` : "brand"}>
      <AcadraMark size={30} className="brand-mark" />
      <span className="brand-wordmark">acadra</span>
    </span>
  );
}
