document.addEventListener('DOMContentLoaded', () => {
    const carouselContainer = document.getElementById('lotes-carousel-container');
    if (!carouselContainer) {
        console.error('Error: Carousel container #lotes-carousel-container not found.');
        return;
    }

    const userId = carouselContainer.dataset.userId;
    if (!userId || userId === 'None') {
        // No need to show an error, the user might just not be logged in or it's not their profile
        return;
    }

    loadLotes(userId);
});

async function loadLotes(userId) {
    const carousel = document.getElementById('lotes-carousel');
    if (!carousel) return;

    try {
        const response = await fetch(`/api/lotes/${userId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        const lotes = data.success ? data.lotes : (Array.isArray(data) ? data : []);
        renderLotesCarousel(lotes);
    } catch (error) {
        console.error('Error loading lotes:', error);
        carousel.innerHTML = `<p class="text-red-500 col-span-full">Error al cargar lotes.</p>`;
    }
}

function renderLotesCarousel(lotes) {
    const carousel = document.getElementById('lotes-carousel');
    if (!carousel) return;

    carousel.innerHTML = '';

    if (!lotes || lotes.length === 0) {
        carousel.innerHTML = '<p class="text-gray-500 col-span-full">Este usuario no tiene lotes registrados.</p>';
        return;
    }

    lotes.forEach(lote => {
        const loteButton = document.createElement('a');
        loteButton.href = `/gestionar-lote?lote_id=${lote.id}`;
        loteButton.className = 'flex-shrink-0 w-20 h-14 bg-white rounded-lg shadow-md p-1 flex flex-col items-center justify-center text-center hover:shadow-lg hover:bg-yellow-50 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-yellow-500';

        loteButton.innerHTML = `
            <span class="text-lg font-bold text-yellow-500">${lote.orden_miel}</span>
            <span class="text-xs font-semibold text-gray-700 break-words overflow-hidden text-ellipsis">${lote.nombre_miel}</span>
        `;

        carousel.appendChild(loteButton);
    });
}
