import { DRAWINGS } from '../src/demo/data.ts';
import { resolveDemo } from '../src/demo/engine.ts';
const questions = [
  'How many doors are shown?',
  'How many windows are shown?',
  'What is the net area of Bedroom 01?',
  'How wide is the corridor?',
  'What is the width of door D03?',
  'What is the fire rating?',
  'How many doors are in the entire building?',
];
console.log(
  JSON.stringify(
    DRAWINGS.flatMap((drawing) =>
      questions.map((question) => resolveDemo(drawing, question, 'en').result),
    ),
  ),
);
