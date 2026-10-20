// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC1271 {
    function isValidSignature(bytes32 digest, bytes calldata signature) external view returns (bytes4);
}

/// @notice EIP-7702 delegation and smart accounts make code.length == 0 an
/// unreliable proxy for ownership or externally owned accounts.
contract CodeLengthGate {
    function eoaOnlyAction() external view {
        require(msg.sender.code.length == 0, "contract caller");
    }
}

/// @notice Authorize an explicit principal, which can be an EOA, a delegated
/// account, or a smart-account contract. Do not use tx.origin for this check.
contract ExplicitPrincipalGate {
    address public immutable principal;

    constructor(address principal_) {
        principal = principal_;
    }

    function action() external view {
        require(msg.sender == principal, "principal only");
    }
}

/// @notice Contract owners can validate signatures through EIP-1271 rather
/// than assuming the signer has no code.
contract Eip1271SignatureGate {
    bytes4 private constant MAGIC_VALUE = 0x1626ba7e;
    address public immutable signer;

    constructor(address signer_) {
        signer = signer_;
    }

    function valid(bytes32 digest, bytes calldata signature) external view returns (bool) {
        (bool ok, bytes memory result) = signer.staticcall(
            abi.encodeCall(IERC1271.isValidSignature, (digest, signature))
        );
        return ok && result.length >= 32 && abi.decode(result, (bytes4)) == MAGIC_VALUE;
    }
}
