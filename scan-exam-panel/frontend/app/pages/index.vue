<template>
  <UContainer class="py-10 sm:py-14">
    <div class="mx-auto max-w-3xl space-y-10">
      <div class="space-y-3">
        <p class="text-sm font-medium text-primary">
          Panel docente
        </p>
        <h1 class="text-3xl font-semibold tracking-tight text-highlighted sm:text-4xl">
          Subir evaluación
        </h1>
        <p class="text-muted text-pretty sm:text-lg">
          Sube las imágenes de las fichas e indica los estudiantes y la clave de respuestas
          a mano o importando un CSV. Todo se enviará como multipart/form-data a la API.
        </p>
      </div>

      <section class="space-y-4">
        <h2 class="text-lg font-semibold text-highlighted">
          Datos del examen
        </h2>
        <UploadExamPackageForm />
      </section>
    </div>
  </UContainer>
</template>
