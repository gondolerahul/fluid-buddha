// The live demo page: the questions to try and the capabilities they reveal.
// Topics match lib/answers.ts, so a capability lights up when its answer is given.

export const DEMO_QUESTIONS = [
  { label: "How much does it cost?" },
  { label: "Show me how it works" },
  { label: "क्या ये हिंदी में बात करता है?", hi: true },
  { label: "Who will win the IPL this year?" },
  { label: "Book a demo" },
];

export const CAPABILITIES = [
  { topic: "price", title: "It talks and shows", body: "Answers out loud, with a pricing table." },
  { topic: "how", title: "It explains your product", body: "In plain words, from your pages." },
  { topic: "hindi", title: "English and Hindi", body: "Even when your site is in English only." },
  { topic: "unknown", title: "It does not guess", body: "If it is not on your site, it says so." },
  { topic: "book", title: "It books meetings", body: "Only after the visitor says yes." },
];
