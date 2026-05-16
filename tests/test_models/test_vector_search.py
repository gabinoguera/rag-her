import pytest

# Pendiente EPIC-002: Document model eliminado en RAG-05.
# Este fichero se reescribirá cuando EPIC-002 cree los nuevos modelos (Employee, CheckIn, CheckInChunk).

pytestmark = pytest.mark.skip(reason="Pendiente EPIC-002: modelos legacy eliminados, nuevos modelos aún no creados")


def test_placeholder():
    pass
