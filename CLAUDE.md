# Global Claude Instructions

## Plan Mode Before Implementation

**Prima di implementare qualsiasi richiesta non banale:**

1. **Valuta la complessità** della richiesta dell'utente
2. **Se la richiesta richiede**:
   - Modifiche a più file
   - Decisioni architetturali
   - Nuove funzionalità
   - Refactoring significativo

   → **Entra in Plan Mode** (`EnterPlanMode`) per pianificare gli step necessari

3. **In Plan Mode**:
   - Esplora il codebase per capire il contesto
   - Identifica i file da modificare
   - Definisci gli step di implementazione
   - Presenta il piano all'utente per approvazione
   - Solo dopo approvazione, procedi con l'implementazione

4. **Eccezioni** (non serve Plan Mode):
   - Fix banali (typo, singola riga)
   - Query informative
   - Comandi espliciti e semplici

## Principi Generali

- **KISS**: Keep It Simple, Stupid
- **YAGNI**: You Aren't Gonna Need It
- Non over-engineerare
- Preferisci modifiche minimali e incrementali

## Testing Requirements (MANDATORY)

**Ogni implementazione deve includere test:**

1. **Unit Tests**: Test per funzioni/classi individuali
2. **Integration Tests**: Test per componenti che interagiscono
3. **E2E Tests (quando applicabile)**:
   - Testa il flusso completo end-to-end
   - Usa dati reali quando possibile (non solo mock)
   - Verifica comportamento in condizioni realistiche

**Prima di considerare un task completato:**
- [ ] Unit tests passano
- [ ] Integration tests passano
- [ ] E2E tests con dati reali (se applicabile)
- [ ] Coverage adeguata per codice critico

**Pattern consigliato:**
```python
# tests/e2e/test_feature_e2e.py
@pytest.mark.e2e
def test_complete_flow_with_real_data():
    """Test end-to-end con dati reali."""
    # Setup con dati reali (non mock)
    # Esegui il flusso completo
    # Verifica risultati
```

## Project Validation System

**Ogni progetto DEVE avere una validation config** per `/spec-pipeline`.

### Setup (una tantum per progetto)

```bash
# Crea struttura validation
mkdir -p .claude/validation

# Copia template e personalizza
cp ~/.claude/templates/validation-config.json .claude/validation/config.json
```

### File richiesti

```
{progetto}/
└── .claude/
    └── validation/
        └── config.json    # OBBLIGATORIO per /spec-pipeline
```

### Config minima

```json
{
  "domain": "your-domain",
  "anti_patterns": [],
  "research_keywords": {
    "trigger": [],
    "skip": []
  }
}
```

### Riferimenti

- **Template**: `~/.claude/templates/validation-config.json`
- **Esempi**: nautilus_dev, UTXOracle, N8N_dev
- **Comando**: `/new-project` per scaffold completo
