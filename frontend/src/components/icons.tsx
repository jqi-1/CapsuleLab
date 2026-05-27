type IconProps = {
  className?: string;
};

function Svg({ children, className }: React.PropsWithChildren<IconProps>) {
  return (
    <svg
      className={className ?? "h-4 w-4"}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export function BoxIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m21 8-9-5-9 5 9 5 9-5Z" />
      <path d="m3 8 9 5v8l9-5V8" />
      <path d="M12 13v8" />
    </Svg>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </Svg>
  );
}

export function PlayIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m8 5 11 7-11 7V5Z" />
    </Svg>
  );
}

export function StopIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </Svg>
  );
}

export function HammerIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m15 12-8.5 8.5a2.1 2.1 0 0 1-3-3L12 9" />
      <path d="m17 10 4-4-3-3-4 4" />
      <path d="m8 4 12 12" />
    </Svg>
  );
}

export function RefreshIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M20 11a8.1 8.1 0 0 0-15.5-2M4 5v4h4" />
      <path d="M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4" />
    </Svg>
  );
}

export function TerminalIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m7 8 4 4-4 4" />
      <path d="M13 16h4" />
      <rect x="3" y="4" width="18" height="16" rx="2" />
    </Svg>
  );
}

export function ExternalIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M14 3h7v7" />
      <path d="M10 14 21 3" />
      <path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" />
    </Svg>
  );
}

export function TrashIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 6h18" />
      <path d="M8 6V4h8v2" />
      <path d="m19 6-1 15H6L5 6" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
    </Svg>
  );
}

export function GlobeIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a14 14 0 0 1 0 18" />
      <path d="M12 3a14 14 0 0 0 0 18" />
    </Svg>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m5 13 4 4L19 7" />
    </Svg>
  );
}

export function AlertIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
    </Svg>
  );
}

export function ActivityIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 12h4l3-8 4 16 3-8h4" />
    </Svg>
  );
}

export function GitBranchIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="6" cy="6" r="2" />
      <circle cx="18" cy="6" r="2" />
      <circle cx="6" cy="18" r="2" />
      <path d="M6 8v8" />
      <path d="M8 6h6a4 4 0 0 1 4 4v6" />
    </Svg>
  );
}

export function GraphIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="6" cy="7" r="2.5" />
      <circle cx="18" cy="6" r="2.5" />
      <circle cx="17" cy="18" r="2.5" />
      <circle cx="6" cy="17" r="2.5" />
      <path d="m8.4 6.8 7.2-.6" />
      <path d="m7.9 9.1 7.2 6.7" />
      <path d="m8.5 17.2 6-.1" />
      <path d="m18 8.5-.8 7" />
    </Svg>
  );
}

export function UploadIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3v12" />
      <path d="m7 8 5-5 5 5" />
      <path d="M5 21h14" />
    </Svg>
  );
}

export function DownloadIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 15V3" />
      <path d="m7 10 5 5 5-5" />
      <path d="M5 21h14" />
    </Svg>
  );
}

export function CpuIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="7" y="7" width="10" height="10" rx="2" />
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 15h3M1 9h3M1 15h3" />
    </Svg>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m9 18 6-6-6-6" />
    </Svg>
  );
}

export function SettingsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3" />
      <path d="M12 19v3" />
      <path d="M2 12h3" />
      <path d="M19 12h3" />
      <path d="m4.9 4.9 2.1 2.1" />
      <path d="m17 17 2.1 2.1" />
      <path d="m4.9 19.1 2.1-2.1" />
      <path d="m17 7 2.1-2.1" />
    </Svg>
  );
}
