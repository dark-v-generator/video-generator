window.onload = function () {
    const urlParams = new URLSearchParams(window.location.search);
    const showLoading = urlParams.get('show_loading');

    if (showLoading?.toLowerCase() === 'true') {
        updateProgressBar();
    }
}


function updateProgressBar() {
    const interval = setInterval(() => {
        fetch(`/bars_progress/`)
            .then(response => response.json())
            .then(data => {
                for (let task_id in data) {
                    const progressBar = document.getElementById(task_id);
                    if (progressBar !== null) {
                        progressBar.value = data[task_id].index;
                        progressBar.max = data[task_id].total;

                        if (data[task_id].index == data[task_id].total) {
                            clearInterval(interval);
                            const url = new URL(window.location.href);
                            url.searchParams.delete('show_loading');
                            window.location.replace(url.toString())
                        }
                    }
                };
            })
    }, 2000)
}

function deleteCaption(i) {
    const captionElement = document.getElementById(`caption-segment-${i}`);
    if (captionElement) {
        captionElement.remove();
    }
}

function deleteHistory(redditHistoryID) {
    if (confirm("Você tem certeza que deseja deletar esta história?")) {
        fetch(`/history/delete/${redditHistoryID}`, {
            method: 'POST',
        })
            .then(response => {
                if (response.ok) {
                    window.location.href = '/';
                } else {
                    alert('Erro ao deletar a história.');
                }
            })
            .catch(error => {
                console.error('Erro:', error);
                alert('Erro ao deletar a história.');
            });
    }
}

