"""Capability 7: multilingual and mixed-language queries."""
from tests.live.runner import Case, language_is, not_crashed_and_answered, all_of

TITLE = "Multilingual and mixed-language queries"
CAPABILITY_NUMBER = 7

CASES = [
    Case("01", "Spanish question, should be detected and answered in Spanish",
         ["¿Cuáles fueron los ingresos de Middle Americas en el primer trimestre de 2024?"],
         all_of(language_is("es"), not_crashed_and_answered())),

    Case("02", "French question",
         ["Quelle était la marge EBITDA en EMEA au deuxième trimestre 2025?"],
         all_of(language_is("fr"), not_crashed_and_answered())),

    Case("03", "German question",
         ["Wie hoch war der Umsatz von Nordamerika im ersten Quartal 2024?"],
         not_crashed_and_answered()),

    Case("04", "Portuguese question (relevant given Brazil/South America data)",
         ["Qual foi a receita da América do Sul em 2025?"], not_crashed_and_answered()),

    Case("05", "mixed-language: Hindi-English code-switching",
         ["South America ka revenue Q3 2025 mein kitna tha?"], not_crashed_and_answered()),

    Case("06", "mixed-language: Spanish-English code-switching",
         ["Cual fue el revenue de North America en Q1 2024?"], not_crashed_and_answered()),

    Case("07", "English question as a control case (should stay in English)",
         ["What was North America's revenue in Q1 2024?"], language_is("en")),

    Case("08", "non-English capability-intro request",
         ["¿Qué puedes hacer?"], not_crashed_and_answered()),
]
