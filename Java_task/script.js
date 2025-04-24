function convert() {
  const input = document.getElementById("inputField").value;
  const resultDiv = document.getElementById("result");

  fetch(`http://localhost:8080/convert-measurements?input=${encodeURIComponent(input)}`)
    .then(response => {
      if (!response.ok) throw new Error("Server error");
      return response.json();
    })
    .then(data => {
      resultDiv.innerHTML = `<strong>Result:</strong> ${JSON.stringify(data)}`;
    })
    .catch(error => {
      resultDiv.innerHTML = `<span style="color:red;">Error: ${error.message}</span>`;
    });
}

function showHistory() {
  const resultDiv = document.getElementById("result");

  fetch(`http://localhost:8080/history`)
    .then(response => {
      if (!response.ok) throw new Error("Server error");
      return response.json();
    })
    .then(data => {
      resultDiv.innerHTML = `<strong>History:</strong><br>${JSON.stringify(data)}`;
    })
    .catch(error => {
      resultDiv.innerHTML = `<span style="color:red;">Error: ${error.message}</span>`;
    });
}

function clearResult() {
  document.getElementById("result").innerHTML = "";
}
