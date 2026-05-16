#!/bin/bash
# Hook: user-prompt-submit
# Ejecutado antes de procesar cada prompt del usuario
# Variables disponibles: $CLAUDE_USER_PROMPT, $CLAUDE_WORKING_DIR

# Validar que estamos en el directorio correcto del proyecto
if [[ ! -f "manage.py" ]]; then
    echo "⚠️  Warning: Not in Django project root directory"
    exit 1
fi

# Verificar que los archivos .env necesarios existen
if [[ ! -f ".env" ]]; then
    echo "⚠️  Warning: .env file not found"
    exit 1
fi

# Todo OK
exit 0
