import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(scriptDir, '..');

const files = {
  planGallery: readFileSync(resolve(frontendRoot, 'src/pages/PlanGalleryPage/PlanGalleryPage.tsx'), 'utf8'),
  parcelMap: readFileSync(resolve(frontendRoot, 'src/components/map/ParcelMap.tsx'), 'utf8'),
  deckMap: readFileSync(resolve(frontendRoot, 'src/components/map/DeckGLMap/DeckGLMap.tsx'), 'utf8'),
  homePage: readFileSync(resolve(frontendRoot, 'src/pages/HomePage/HomePage.tsx'), 'utf8'),
  css: readFileSync(resolve(frontendRoot, 'src/pages/PlanGalleryPage/PlanGalleryPage.css'), 'utf8'),
};

const expectations = [
  {
    label: 'ParcelMap exposes an onParcelHover callback prop',
    passed: /onParcelHover\?:\s*\(/.test(files.parcelMap) && /onParcelHover\(apn,\s*props,\s*feature\)/.test(files.parcelMap),
  },
  {
    label: 'DeckGLMap exposes an onParcelHover callback prop',
    passed: /onParcelHover\?:\s*\(/.test(files.deckMap) && /onParcelHover\(apn,\s*properties,/.test(files.deckMap),
  },
  {
    label: 'PlanGallery requests pinned assignment explanations through apiClient',
    passed:
      /apiClient\s*\.\s*explainSpatialAssignment/.test(files.planGallery) &&
      /handlePlanParcelSelect/.test(files.planGallery),
  },
  {
    label: 'PlanGallery passes hover and click handlers to both map modes',
    passed:
      (files.planGallery.match(/onParcelHover=\{handlePlanParcelHover\}/g) || []).length >= 2 &&
      (files.planGallery.match(/onParcelSelect=\{handlePlanParcelSelect\}/g) || []).length >= 2,
  },
  {
    label: 'PlanGallery renders hover preview and pinned explanation UI',
    passed:
      /plan-assignment-hover/.test(files.planGallery) &&
      /plan-assignment-explanation/.test(files.planGallery) &&
      /\.plan-assignment-hover/.test(files.css) &&
      /\.plan-assignment-explanation/.test(files.css),
  },
  {
    label: 'Environmental page does not show generated-plan assignment mismatch errors',
    passed:
      !/No generated assignment found/.test(files.homePage) &&
      /showAssignmentExplanation=\{false\}/.test(files.homePage),
  },
];

const failed = expectations.filter((expectation) => !expectation.passed);

if (failed.length > 0) {
  for (const expectation of failed) {
    console.error(`FAIL: ${expectation.label}`);
  }
  process.exit(1);
}

for (const expectation of expectations) {
  console.log(`PASS: ${expectation.label}`);
}
