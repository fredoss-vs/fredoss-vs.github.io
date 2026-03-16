const year = document.getElementById("year");
if (year) {
  year.textContent = new Date().getFullYear().toString();
}

const elements = document.querySelectorAll(".reveal");
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("show");
      }
    });
  },
  { threshold: 0.16 }
);

elements.forEach((element, index) => {
  element.style.transitionDelay = `${Math.min(index * 70, 420)}ms`;
  observer.observe(element);
});
