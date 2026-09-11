FROM ghcr.io/nvidia/openshell/supervisor:0.0.97 AS supervisor

FROM ghcr.io/aaif-goose/goose:1.43.0

# Switch to root user.
# This is needed for openshell-sandbox. It will run goose as non-root user.
USER root

RUN apt update && apt install iproute2 nftables curl -y
RUN mkdir -p /var/log
RUN mkdir -p /sandbox
RUN chown -R goose:goose /sandbox

RUN mkdir -p /etc/openshell
COPY container-images/openshell/opa.rego /etc/openshell/opa.rego

COPY --from=supervisor /openshell-sandbox /openshell-sandbox

ENTRYPOINT ["/openshell-sandbox"]
