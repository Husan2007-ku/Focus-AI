"""
So'rov-korrelyatsiya ID middleware'i.

Maqsad: har bir HTTP so'rovga unikal `request_id` biriktirish va uni butun
so'rov davomida chiqadigan BARCHA log yozuvlariga (structlog contextvars
orqali) avtomatik qo'shish. Bu productionda bitta foydalanuvchi shikoyatini
(masalan, "500 xato oldim") loglardan aniq bitta so'rov zanjiriga bog'lab
topishni osonlashtiradi -- aks holda bir vaqtning o'zida kelgan yuzlab
so'rovlar logi bir-biriga aralashib ketadi.

Agar client o'zi `X-Request-ID` header yuborgan bo'lsa (masalan, frontend
yoki boshqa mikroservis), o'sha qiymat ishlatiladi -- shunda butun tizim
bo'ylab (frontend -> backend -> tashqi xizmat) bitta ID kuzatiladi. Aks
holda yangi UUID yaratiladi.
"""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # contextvars.bind_contextvars -- shu so'rov tugaguncha chaqiriladigan
        # barcha logger.info/warning/error chaqiruvlariga avtomatik
        # `request_id=...` maydonini qo'shadi (qarang: app/core/logging.py
        # dagi `merge_contextvars` processor).
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
