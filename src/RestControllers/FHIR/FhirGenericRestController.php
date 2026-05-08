<?php

/*
 * FhirGenericRestController.php
 * @package openemr
 * @link      https://www.open-emr.org
 * @author    Stephen Nielson <snielson@discoverandchange.com>
 * @copyright Copyright (c) 2025 Stephen Nielson <snielson@discoverandchange.com>
 * @license   https://github.com/openemr/openemr/blob/master/LICENSE GNU General Public License 3
 */

namespace OpenEMR\RestControllers\FHIR;

use OpenEMR\Common\Http\HttpRestRequest;
use OpenEMR\Core\OEGlobalsBag;
use OpenEMR\FHIR\R4\PHPFHIRResponseParser;
use OpenEMR\FHIR\R4\FHIRResource\FHIRBundle\FHIRBundleEntry;
use OpenEMR\FHIR\R4\FHIRResource\FHIRDomainResource;
use OpenEMR\FHIR\SMART\ResourceConstraintFilterer;
use OpenEMR\RestControllers\Config\RestConfig;
use OpenEMR\RestControllers\RestControllerHelper;
use OpenEMR\Services\FHIR\FhirResourcesService;
use OpenEMR\Services\FHIR\FhirServiceBase;
use OpenEMR\Services\IGlobalsAware;
use OpenEMR\Services\Trait\GlobalInterfaceTrait;
use OpenEMR\Validators\ProcessingResult;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Response;

class FhirGenericRestController implements IGlobalsAware {

    use GlobalInterfaceTrait;
    private FhirResourcesService $fhirResourcesService;

    private array $aclChecks = [];

    private ResourceConstraintFilterer $resourcePolicyEnforcementDecisionChecker;

    public function __construct(protected HttpRestRequest $request, protected FhirServiceBase $fhirService, OEGlobalsBag $globalsBag)
    {
        $this->setGlobalsBag($globalsBag);
    }

    public function getResourcePolicyEnforcementDecisionChecker(): ResourceConstraintFilterer {
        // TODO: eventually we could inject the ACLs here and do more advanced checking on a per-resource basis
        if (!isset($this->resourcePolicyEnforcementDecisionChecker)) {
            $this->resourcePolicyEnforcementDecisionChecker = new ResourceConstraintFilterer();
        }
        return $this->resourcePolicyEnforcementDecisionChecker;
    }

    public function addAclRestrictions(string $section, string $subSection = '', string $aclPermission = '') : void {
        $this->aclChecks[] = ['section' => $section, 'subSection' => $subSection, 'aclPermission' => $aclPermission];
    }

    private function enforceAclRestrictions(): void
    {
        if ($this->getHttpRestRequest()->isPatientRequest()) {
            return;
        }

        foreach ($this->aclChecks as $aclCheck) {
            RestConfig::request_authorization_check($this->getHttpRestRequest(), $aclCheck['section'], $aclCheck['subSection'], $aclCheck['aclPermission']);
        }
    }

    protected function getFhirResourcesService(): FhirResourcesService
    {
        if (!isset($this->fhirResourcesService)) {
            $this->fhirResourcesService = new FhirResourcesService();
        }
        return $this->fhirResourcesService;
    }

    public function getHttpRestRequest(): HttpRestRequest
    {
        return $this->request;
    }

    public function getFhirService(): FhirServiceBase
    {
        return $this->fhirService;
    }

    /**
     * Queries for a single FHIR condition resource by FHIR id
     * @param string $fhirId The FHIR condition resource id (uuid)
     * @returns Response 200 if the operation completes successfully
     */
    public function getOne(string $fhirId): Response
    {
        // security constraints are added as additional query parameters here
        // so that the same processing logic can be used for both single resource
        // and multiple resource retrieval
        // that is why we override the _id parameter and pass along any other query parameters
        // while this means that a 404 will be returned instead of a 401, that's ok.
        // TODO: consider changing status code to 401 in the future if needed
        $queryParams = $this->getHttpRestRequest()->query->all();
        $queryParams['_id'] = $fhirId;
        $processingResult = $this->getAllProcessingResult($queryParams);

        return RestControllerHelper::handleFhirProcessingResult($processingResult, 200);
    }

    protected function getAllProcessingResult(array $searchParams): ProcessingResult {
        if ($this->getHttpRestRequest()->isPatientRequest()) {
            $puuidBind = $this->getHttpRestRequest()->getPatientUUIDString();
        } else {
            $this->enforceAclRestrictions();
            $puuidBind = null;
        }
        $filteredProcessingResult = new ProcessingResult();
        $searchResult = $this->getFhirService()->getAll($searchParams, $puuidBind);
        if ($searchResult->isValid() && $searchResult->hasData()) {
            foreach ($searchResult->getData() as $resource) {
                if ($this->canAccessResource($resource)) {
                    $filteredProcessingResult->addData($resource);
                }
            }
        } else {
            $filteredProcessingResult = $searchResult;
        }
        return $filteredProcessingResult;
    }

    /**
     * Queries for FHIR condition resources using various search parameters.
     * @param array $searchParams
     * @return JsonResponse|Response FHIR bundle with query results, if found
     */
    public function getAll(?array $searchParams = null): JsonResponse|Response
    {
        if (empty( $searchParams)) {
            $searchParams = $this->request->query->all();
        }
        $redirectUrl = $this->getHttpRestRequest()->getServerParams()['REDIRECT_URL'] ?? '';
        $bundleEntries = [];
        $resourceName = 'FhirDomainResource';
        $processingResult = $this->getAllProcessingResult($searchParams);
        foreach ($processingResult->getData() as $searchResult) {
            $bundleEntry = [
                'fullUrl' =>  $this->getGlobalsBag()->get('site_addr_oath') . $redirectUrl . '/' . $searchResult->getId(),
                'resource' => $searchResult
            ];
            if ($searchResult instanceof FHIRDomainResource) {
                $resourceName = $searchResult->get_fhirElementName();
            }
            $fhirBundleEntry = new FHIRBundleEntry($bundleEntry);
            array_push($bundleEntries, $fhirBundleEntry);
        }
        $bundleSearchResult = $this->getFhirResourcesService()->createBundle($resourceName, $bundleEntries, false);
        $searchResponseBody = RestControllerHelper::responseHandler($bundleSearchResult, null, 200);
        return $searchResponseBody;
    }

    public function post(): Response
    {
        $this->enforceAclRestrictions();

        $validationResult = new ProcessingResult();
        try {
            $payload = json_decode($this->getHttpRestRequest()->getContent(), true, 512, JSON_THROW_ON_ERROR);
            if (!is_array($payload)) {
                $validationResult->setValidationMessages(['resource' => 'FHIR JSON object is required']);
                return RestControllerHelper::handleFhirProcessingResult($validationResult, Response::HTTP_CREATED);
            }

            $resource = (new PHPFHIRResponseParser())->parse(json_encode($payload, JSON_THROW_ON_ERROR));
            if (!$resource instanceof FHIRDomainResource) {
                $validationResult->setValidationMessages(['resource' => 'FHIR domain resource is required']);
                return RestControllerHelper::handleFhirProcessingResult($validationResult, Response::HTTP_CREATED);
            }
            $patientScopeValidation = $this->validatePatientWriteScope($resource);
            if ($patientScopeValidation instanceof ProcessingResult) {
                return RestControllerHelper::handleFhirProcessingResult($patientScopeValidation, Response::HTTP_CREATED);
            }
        } catch (\Throwable $exception) {
            $validationResult->setValidationMessages(['resource' => $exception->getMessage()]);
            return RestControllerHelper::handleFhirProcessingResult($validationResult, Response::HTTP_CREATED);
        }

        try {
            $processingResult = $this->getFhirService()->insert($resource);
        } catch (\Throwable $exception) {
            $processingResult = new ProcessingResult();
            $processingResult->setInternalErrors([$exception->getMessage()]);
        }

        return RestControllerHelper::handleFhirProcessingResult($processingResult, Response::HTTP_CREATED);
    }

    private function validatePatientWriteScope(FHIRDomainResource $resource): ?ProcessingResult
    {
        if (!$this->getHttpRestRequest()->isPatientRequest()) {
            return null;
        }

        $processingResult = new ProcessingResult();
        if (!method_exists($resource, 'getSubject')) {
            $processingResult->setValidationMessages(['subject' => 'Patient-scoped create requires a subject reference']);
            return $processingResult;
        }

        $subject = $resource->getSubject();
        $reference = is_object($subject) && method_exists($subject, 'getReference') ? (string)$subject->getReference() : '';
        if (!preg_match('#Patient/([^/?]+)#', $reference, $matches)) {
            $processingResult->setValidationMessages(['subject' => 'Patient-scoped create requires a Patient subject reference']);
            return $processingResult;
        }

        if ($matches[1] !== $this->getHttpRestRequest()->getPatientUUIDString()) {
            $processingResult->setValidationMessages(['subject' => 'Patient subject does not match the patient access token']);
            return $processingResult;
        }

        return null;
    }

    public function canAccessResource(FHIRDomainResource $resource): bool {
        return $this->getResourcePolicyEnforcementDecisionChecker()->canAccessResource($resource, $this->getHttpRestRequest());
    }
}
