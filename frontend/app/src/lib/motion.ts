export const cardMotion = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } }
};

export const listStagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } }
};
