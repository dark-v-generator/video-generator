window.onload = updateProgressBar

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
                    }
                };
            })
    }, 500)
}

// TODO remove this
function startProcessing() {
    fetch('/process').then(_ => location.reload())
}