export const PUBLIC_SITE = {
  product: "COMPASS",
  institution: "University of Camarines Norte",
  office: "Guidance and Counseling Office",
  accountHref: "/login",
  accountLabel: "Sign in to COMPASS",
} as const;

export const PUBLIC_NAVIGATION = [
  { href: "/", label: "Home" },
  { href: "/about", label: "About" },
  { href: "/services", label: "Services" },
  { href: "/announcements", label: "Announcements" },
  { href: "/resources", label: "Resources" },
  { href: "/contact", label: "Contact" },
] as const;

export const LANDING_PAGE = {
  hero: {
    title: "Guidance for the",
    highlight: "path ahead.",
    description:
      "Find guidance services, office updates, and helpful resources for UCNians at every step.",
    primaryAction: {
      href: PUBLIC_SITE.accountHref,
      label: PUBLIC_SITE.accountLabel,
    },
    secondaryAction: {
      href: "#start-here",
      label: "Explore support",
    },
  },
  start: {
    eyebrow: "Start here",
    title: "Find what you need",
    description: "Choose what you need help with.",
    items: [
      {
        title: "Explore guidance services",
        body: "Learn about the support available through the Guidance and Counseling Office.",
        href: "/services",
        link: "Explore services",
      },
      {
        title: "Stay up to date",
        body: "Read announcements and reminders for UCNians from the Guidance and Counseling Office.",
        href: "/announcements",
        link: "Read announcements",
      },
      {
        title: "Browse helpful resources",
        body: "Find guides, links, and materials to help you move forward as a UCNian.",
        href: "/resources",
        link: "Browse resources",
      },
    ],
  },
  announcements: {
    eyebrow: "Stay informed",
    title: "Announcements",
    description: "Important updates and reminders for UCNians from the Guidance and Counseling Office.",
    link: "See all announcements",
    href: "/announcements",
  },
  guidance: {
    eyebrow: "Guidance support",
    title: "Find the support you need",
    description:
      "Not sure where to begin? Learn more about the Guidance and Counseling Office and how to ask for support.",
    href: "/services",
    link: "Explore services",
  },
  resources: {
    eyebrow: "Helpful resources",
    title: "Resources",
    description:
      "Guides, links, and downloadable materials to support UCNians in their studies, wellbeing, and next steps.",
    link: "Browse all resources",
    href: "/resources",
  },
  office: {
    eyebrow: PUBLIC_SITE.office,
    title: "Here for every UCNian",
    description:
      "Sign in to continue with COMPASS, or contact the Guidance and Counseling Office if you’re not sure where to begin.",
    primaryAction: {
      href: PUBLIC_SITE.accountHref,
      label: PUBLIC_SITE.accountLabel,
    },
    secondaryAction: {
      href: "/contact",
      label: "Contact the office",
    },
  },
} as const;

export const PUBLIC_FOOTER_GROUPS = [
  {
    title: "Explore",
    links: PUBLIC_NAVIGATION.slice(1, 4),
  },
  {
    title: "Support",
    links: [
      { href: "/resources", label: "Resources" },
      { href: "/contact", label: "Contact the office" },
      { href: "/login", label: "Sign in to COMPASS" },
    ],
  },
] as const;
