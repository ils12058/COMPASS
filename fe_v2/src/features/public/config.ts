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
    eyebrow: PUBLIC_SITE.office,
    title: "Guidance for the",
    highlight: "path ahead.",
    description:
      "Find Guidance and Counseling Office announcements, resources, and a clear way into COMPASS when you need university support.",
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
    description: "Choose a place to begin.",
    items: [
      {
        title: "Explore Guidance services",
        body: "Learn what COMPASS connects you to, then sign in to see the options available to your account.",
        href: "/services",
        link: "Explore support",
      },
      {
        title: "Read office updates",
        body: "See public announcements shared by the Guidance and Counseling Office.",
        href: "/announcements",
        link: "View announcements",
      },
      {
        title: "Find guidance resources",
        body: "Browse public articles, links, and downloadable materials curated for the university community.",
        href: "/resources",
        link: "Browse resources",
      },
    ],
  },
  announcements: {
    eyebrow: "Stay informed",
    title: "Announcements",
    description: "Updates and reminders from the Guidance and Counseling Office.",
    link: "View all announcements",
    href: "/announcements",
    items: [
      {
        category: "Office update",
        title: "A place to begin",
        body: "Start with the support guide when you are not sure which office service fits your concern.",
        href: "/announcements",
        tone: "butter",
        rotation: "left",
      },
      {
        category: "Student support",
        title: "You do not have to figure it out alone",
        body: "COMPASS brings the next helpful step closer to the university community.",
        href: "/announcements",
        tone: "sage",
        rotation: "right",
      },
      {
        category: "Keep close",
        title: "Support starts with a conversation",
        body: "Explore the public resources, then sign in when you are ready for account-specific services.",
        href: "/announcements",
        tone: "rose",
        rotation: "left",
      },
    ],
  },
  guidance: {
    eyebrow: "Guidance support",
    title: "A clearer path to office services",
    description:
      "COMPASS brings Guidance and Counseling Office access into one university platform. Public pages explain the basics; signed-in users can view the services and actions available to their account.",
    href: "/services",
    link: "View services",
  },
  resources: {
    eyebrow: "Useful reading",
    title: "Resources",
    description: "Information and materials curated for the university community.",
    link: "Browse all resources",
    href: "/resources",
    items: [
      {
        category: "Getting started",
        title: "Know where to begin",
        body: "A simple guide to finding the right Guidance and Counseling Office service.",
        href: "/resources",
      },
      {
        category: "Well-being",
        title: "Make room for your well-being",
        body: "Keep practical support information close when the semester feels full.",
        href: "/resources",
      },
      {
        category: "Student life",
        title: "Resources for the road ahead",
        body: "Explore helpful materials prepared for students, staff, and the wider campus community.",
        href: "/resources",
      },
    ],
  },
  office: {
    eyebrow: PUBLIC_SITE.office,
    title: "Need a way into COMPASS?",
    description:
      "Sign in for account-specific services and options. For public contact guidance, visit the contact page; this site does not publish unverified office hours, phone numbers, or email addresses.",
    primaryAction: {
      href: PUBLIC_SITE.accountHref,
      label: PUBLIC_SITE.accountLabel,
    },
    secondaryAction: {
      href: "/contact",
      label: "Contact guidance",
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
